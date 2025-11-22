# yahoo_token_reader.py
import imaplib
import email
from email.parser import BytesParser
from email.policy import default as default_email_policy
import re
import time
import os
from typing import Optional
import traceback

try:
    import config
except ImportError:
    print("ERRO CRÍTICO em yahoo_token_reader.py: config.py não encontrado.")


    class ConfigFallback:
        YAHOO_EMAIL_ADDRESS = None
        YAHOO_APP_PASSWORD = None
        YAHOO_IMAP_SERVER = "imap.mail.yahoo.com"
        YAHOO_IMAP_PORT = 993


    config = ConfigFallback()

# --- CORREÇÃO DO REMETENTE ---
ESAJ_TOKEN_SENDER = "esaj@tjsp.jus.br"  # <<< REMETENTE CORRETO DO ESAJ
# --- FIM DA CORREÇÃO ---

ESAJ_TOKEN_SUBJECT_KEYWORDS = ["código de validação", "token", "acesso esaj",
                               "validação de login"]  # Mantenha ou ajuste conforme necessário


def extract_token_from_body(body_text: str) -> Optional[str]:
    if not body_text:
        return None
    match = re.search(r'\b(\d{6})\b', body_text)
    if match:
        token = match.group(1)
        print(f"    [TokenReader] Token de 6 dígitos encontrado: {token}")
        return token
    else:
        print("    [TokenReader] Nenhum token de 6 dígitos encontrado no corpo do email.")
        return None


def fetch_esaj_token_from_yahoo(max_retries=3, retry_delay=30, search_limit_minutes=15) -> Optional[str]:
    if not config.YAHOO_EMAIL_ADDRESS or not config.YAHOO_APP_PASSWORD:
        print("  [TokenReader] ERRO: Credenciais do Yahoo não configuradas.")
        return None

    print(f"  [TokenReader] Conectando ao Yahoo: {config.YAHOO_EMAIL_ADDRESS}...")

    for attempt in range(max_retries):
        try:
            mail = imaplib.IMAP4_SSL(config.YAHOO_IMAP_SERVER, config.YAHOO_IMAP_PORT)
            mail.login(config.YAHOO_EMAIL_ADDRESS, config.YAHOO_APP_PASSWORD)
            mail.select("inbox")
            print("  [TokenReader] Login e seleção da INBOX no Yahoo Mail bem-sucedidos.")

            search_criteria_list = []
            if ESAJ_TOKEN_SENDER:
                search_criteria_list.append('FROM')
                search_criteria_list.append(ESAJ_TOKEN_SENDER)

            search_criteria_list.append('UNSEEN')

            if not ESAJ_TOKEN_SENDER:
                print("  [TokenReader] Remetente do eSAJ (ESAJ_TOKEN_SENDER) não configurado. Busca abortada.")
                mail.logout();
                return None

            print(f"  [TokenReader] Executando busca IMAP com critérios: {search_criteria_list}")

            status, data = mail.search(None, *search_criteria_list)

            if status == 'OK':
                mail_ids_bytes = []
                for block in data: mail_ids_bytes.extend(block.split())

                if not mail_ids_bytes:
                    print(f"  [TokenReader] Nenhum email encontrado com os critérios: {search_criteria_list}")
                else:
                    mail_ids_str = [mid.decode() for mid in mail_ids_bytes]
                    print(
                        f"  [TokenReader] IDs de email encontrados ({len(mail_ids_str)}): {mail_ids_str}. Verificando o(s) mais recente(s)...")

                    for email_id_bytes in reversed(mail_ids_bytes):
                        print(f"    [TokenReader] Processando email ID: {email_id_bytes.decode()}")
                        status, msg_data = mail.fetch(email_id_bytes, "(RFC822)")
                        if status == 'OK':
                            for response_part in msg_data:
                                if isinstance(response_part, tuple):
                                    msg = BytesParser(policy=default_email_policy).parsebytes(response_part[1])
                                    subject_decoded = ""
                                    if msg['subject']:
                                        decoded_header = email.header.decode_header(msg['subject'])
                                        for part_text, part_charset in decoded_header:
                                            if isinstance(part_text, bytes):
                                                subject_decoded += part_text.decode(part_charset or 'utf-8', 'ignore')
                                            else:
                                                subject_decoded += part_text
                                    print(f"      Assunto: {subject_decoded}")

                                    subject_match = False
                                    if not ESAJ_TOKEN_SUBJECT_KEYWORDS:
                                        subject_match = True
                                    else:
                                        for keyword in ESAJ_TOKEN_SUBJECT_KEYWORDS:
                                            if keyword.lower() in subject_decoded.lower():
                                                subject_match = True
                                                print(f"      Keyword de assunto '{keyword}' encontrada.")
                                                break

                                    if not subject_match:
                                        print("      Assunto não corresponde às keywords. Pulando este email.")
                                        continue

                                    body_text = ""
                                    if msg.is_multipart():
                                        for part in msg.walk():
                                            content_type = part.get_content_type()
                                            content_disposition = str(part.get("Content-Disposition"))
                                            if "attachment" not in content_disposition and content_type == "text/plain":
                                                charset = part.get_content_charset() or 'utf-8'
                                                payload = part.get_payload(decode=True)
                                                if payload: body_text += payload.decode(charset,
                                                                                        errors='replace'); break
                                    else:
                                        charset = msg.get_content_charset() or 'utf-8'
                                        payload = msg.get_payload(decode=True)
                                        if payload: body_text = payload.decode(charset, errors='replace')

                                    if body_text:
                                        token = extract_token_from_body(body_text)
                                        if token:
                                            mail.logout(); print("  [TokenReader] Logout."); return token
                                        else:
                                            print("      Token não extraído do corpo.")
                                    else:
                                        print("      Corpo de texto plano vazio.")
                        else:
                            print(
                                f"    [TokenReader] Falha ao buscar conteúdo do email ID {email_id_bytes.decode()}. Status: {status}")
                    print(
                        "  [TokenReader] Token não encontrado em nenhum dos emails verificados.")  # Movido para fora do loop de emails
            else:
                print(f"  [TokenReader] Falha ao buscar emails. Status: {status}, Data: {data!r}")

            mail.logout()
            print("  [TokenReader] Logout do Yahoo Mail.")
            if attempt < max_retries - 1:
                print(f"  [TokenReader] Tentativa {attempt + 1}/{max_retries} falhou. Tentando em {retry_delay}s...");
                time.sleep(retry_delay)
            else:
                print(f"  [TokenReader] Token não encontrado após {max_retries} tentativas.");
                return None

        except imaplib.IMAP4.error as e_imap:
            print(f"  [TokenReader] ERRO IMAP (tentativa {attempt + 1}/{max_retries}): {e_imap}")
            if "authentication failed" in str(e_imap).lower(): print("  [TokenReader] Falha autenticação."); return None
            if attempt == max_retries - 1: print("  [TokenReader] Falha final IMAP."); return None
            time.sleep(retry_delay)
        except Exception as e:
            print(f"  [TokenReader] ERRO GERAL (tentativa {attempt + 1}/{max_retries}): {e}")
            traceback.print_exc()
            if attempt == max_retries - 1: print("  [TokenReader] Falha final geral."); return None
            time.sleep(retry_delay)

    return None


if __name__ == "__main__":
    print("--- Testando leitor de token do Yahoo Mail ---")
    print("Certifique-se que seu .env está configurado com YAHOO_EMAIL_ADDRESS e YAHOO_APP_PASSWORD.")
    print("E que você recebeu um email do eSAJ com um token recentemente (marcado como não lido).")
    print(
        f"Procurando por emails NÃO LIDOS de: '{ESAJ_TOKEN_SENDER}' com palavras-chave no assunto: {ESAJ_TOKEN_SUBJECT_KEYWORDS}")

    token = fetch_esaj_token_from_yahoo()
    if token:
        print(f"\nSUCESSO! Token do eSAJ recuperado: {token}")
    else:
        print("\nFALHA: Não foi possível recuperar o token do eSAJ do email.")