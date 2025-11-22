# main.py
import os
import time
import pandas as pd
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException

try:
    import config
    import esaj_scraper
    # Importamos o yahoo_token_reader aqui também, pois a lógica de login no esaj_scraper o utiliza
    import yahoo_token_reader
except ImportError as e:
    print(f"ERRO CRÍTICO em main.py: Falha ao importar um dos módulos do projeto: {e}")
    print(
        "Verifique se todos os arquivos .py (config, esaj_scraper, yahoo_token_reader) estão na mesma pasta e se as bibliotecas foram instaladas.")
    exit("Módulo essencial ausente.")

driver_esaj_global = None
login_esaj_realizado_global = False


def carregar_processos_ja_baixados_do_log() -> set:
    processados = set()
    if os.path.exists(config.ARQUIVO_LOG_ESAJ_PROCESSADOS):
        try:
            with open(config.ARQUIVO_LOG_ESAJ_PROCESSADOS, "r", encoding="utf-8") as f:
                for linha in f:
                    processados.add(linha.strip())
        except Exception as e:
            print(f"Erro ao ler o arquivo de log ({config.ARQUIVO_LOG_ESAJ_PROCESSADOS}): {e}")
    return processados


def marcar_processo_esaj_como_baixado(numero_processo_original: str):
    try:
        with open(config.ARQUIVO_LOG_ESAJ_PROCESSADOS, "a", encoding="utf-8") as f:
            f.write(numero_processo_original + "\n")
        print(f"  [Log eSAJ] Processo '{numero_processo_original}' marcado como baixado no log.")
    except Exception as e:
        print(f"  [Log eSAJ] Erro ao escrever no log ({config.ARQUIVO_LOG_ESAJ_PROCESSADOS}): {e}")


def executar_download_esaj():
    global driver_esaj_global, login_esaj_realizado_global

    print("====================================================")
    print("Iniciando Sistema de Download de Documentos eSAJ")
    print(f"Data e Hora Início: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Lendo planilha de processos eSAJ: {config.CAMINHO_PLANILHA_PROCESSOS_ESAJ}")
    print(f"Pasta de download configurada: {config.PASTA_DOWNLOAD_ESAJ}")
    print(f"Log de processos já baixados: {config.ARQUIVO_LOG_ESAJ_PROCESSADOS}")
    print(f"Tipos de documentos a serem baixados: {config.TIPOS_DOCUMENTO_DESEJADOS_ESAJ}")
    print("----------------------------------------------------")

    try:
        df_processos_esaj = pd.read_excel(config.CAMINHO_PLANILHA_PROCESSOS_ESAJ,
                                          sheet_name=config.NOME_DA_ABA_EXCEL_PROCESSOS_ESAJ,
                                          engine='xlrd' if str(config.CAMINHO_PLANILHA_PROCESSOS_ESAJ).lower().endswith(
                                              '.xls') else None)
        coluna_processo_esaj_encontrada = None
        for palavra_chave in config.PALAVRAS_CHAVE_COLUNA_PROCESSO_ESAJ:
            for col in df_processos_esaj.columns:
                if palavra_chave in str(col).lower():
                    coluna_processo_esaj_encontrada = col
                    break
            if coluna_processo_esaj_encontrada: break

        if not coluna_processo_esaj_encontrada:
            raise ValueError(
                f"Nenhuma coluna com as palavras-chave {config.PALAVRAS_CHAVE_COLUNA_PROCESSO_ESAJ} foi encontrada na planilha de processos eSAJ ('{config.NOME_DA_ABA_EXCEL_PROCESSOS_ESAJ}').")

        numeros_processos_esaj_brutos = df_processos_esaj[coluna_processo_esaj_encontrada].dropna().astype(str).tolist()
        numeros_processos_originais_para_esaj = [
            num.strip() for num in numeros_processos_esaj_brutos
            if isinstance(num, str) and len(''.join(filter(str.isdigit, num.strip()))) >= 15
        ]
        print(
            f"Encontrados {len(numeros_processos_originais_para_esaj)} números de processo (originais da planilha) válidos para processar no eSAJ.")
        if not numeros_processos_originais_para_esaj:
            print("Nenhum número de processo válido na planilha eSAJ para baixar. Encerrando.")
            return
        print(f"Primeiros processos da lista: {numeros_processos_originais_para_esaj[:5]}")
    except FileNotFoundError:
        print(f"ERRO: Planilha de processos eSAJ '{config.CAMINHO_PLANILHA_PROCESSOS_ESAJ}' não encontrada.")
        return
    except Exception as e_excel_esaj:
        print(f"ERRO ao ler a planilha de processos eSAJ: {e_excel_esaj}")
        traceback.print_exc()
        return

    if not driver_esaj_global:
        print("--- Inicializando WebDriver para eSAJ ---")
        try:
            os.makedirs(config.PASTA_DOWNLOAD_ESAJ, exist_ok=True)
            print(f"Arquivos do eSAJ serão baixados em: {config.PASTA_DOWNLOAD_ESAJ}")

            chrome_options_configuradas = esaj_scraper.configurar_chrome_options(config.PASTA_DOWNLOAD_ESAJ)
            service = ChromeService(ChromeDriverManager().install())
            driver_esaj_global = webdriver.Chrome(service=service, options=chrome_options_configuradas)
            print("Navegador para eSAJ iniciado.")
        except WebDriverException as e_wd:
            print(f"ERRO CRÍTICO ao iniciar WebDriver para eSAJ: {e_wd}")
            traceback.print_exc();
            return
        except Exception as e_geral_wd:
            print(f"ERRO GERAL ao iniciar WebDriver para eSAJ: {e_geral_wd}")
            traceback.print_exc();
            return

    if not login_esaj_realizado_global:
        # --- CORREÇÃO AQUI ---
        if config.ESAJ_USER == "SEU_USUARIO_AQUI" or config.ESAJ_PASS == "SUA_SENHA_AQUI":
            # --- FIM DA CORREÇÃO ---
            print(
                "AVISO: Usuário/Senha do eSAJ não parecem estar configurados no config.py ou .env. O login pode falhar.")

        # --- CORREÇÃO AQUI ---
        if esaj_scraper.login_esaj(driver_esaj_global, config.ESAJ_USER, config.ESAJ_PASS):
            # --- FIM DA CORREÇÃO ---
            login_esaj_realizado_global = True
        else:
            print("ERRO CRÍTICO: Falha no login do eSAJ. O script não pode continuar.")
            if driver_esaj_global: driver_esaj_global.quit()
            return

    processos_esaj_ja_baixados = carregar_processos_ja_baixados_do_log()
    print(f"{len(processos_esaj_ja_baixados)} processos eSAJ já constam como baixados no log.")

    for i, num_proc_esaj_original_planilha in enumerate(numeros_processos_originais_para_esaj):
        print(
            f"\n===== INICIANDO DOWNLOAD ESAJ {i + 1}/{len(numeros_processos_originais_para_esaj)}: Processo da Planilha '{num_proc_esaj_original_planilha}' =====")

        if num_proc_esaj_original_planilha in processos_esaj_ja_baixados:
            print(
                f"Processo '{num_proc_esaj_original_planilha}' já foi baixado anteriormente (consta no log). Pulando.")
            continue

        caminho_pdf_baixado_do_esaj = esaj_scraper.download_selected_documents_from_esaj(
            driver_esaj_global,
            num_proc_esaj_original_planilha,
            config.PASTA_DOWNLOAD_ESAJ,
            config.TIPOS_DOCUMENTO_DESEJADOS_ESAJ
        )

        if caminho_pdf_baixado_do_esaj and os.path.exists(caminho_pdf_baixado_do_esaj):
            print(
                f"SUCESSO NO DOWNLOAD: Documentos para '{num_proc_esaj_original_planilha}' baixados em: {caminho_pdf_baixado_do_esaj}")
            marcar_processo_esaj_como_baixado(num_proc_esaj_original_planilha)
        else:
            print(f"FALHA NO DOWNLOAD: Não foi possível baixar os documentos para '{num_proc_esaj_original_planilha}'.")

        print(f"Pausa de 10 segundos antes do próximo processo eSAJ...")
        time.sleep(10)

    print("\n----------------------------------------------------")
    print(f"Todos os processos da planilha eSAJ foram tentados. Concluído às {time.strftime('%Y-%m-%d %H:%M:%S')}.")
    print("====================================================")


if __name__ == "__main__":
    try:
        os.makedirs(config.PASTA_DOWNLOAD_ESAJ, exist_ok=True)
        log_dir = os.path.dirname(config.ARQUIVO_LOG_ESAJ_PROCESSADOS)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        executar_download_esaj()
    except Exception as e_global:
        print("\n----------------------------------------------------")
        print(f"UM ERRO GLOBAL INESPERADO OCORREU NO SCRIPT: {e_global}")
        print(f"Tipo de erro: {type(e_global).__name__}")
        traceback.print_exc()
    finally:
        if driver_esaj_global:
            print("Fechando o navegador do eSAJ no final do script...")
            try:
                driver_esaj_global.quit()
            except Exception as e_quit:
                print(f"Erro ao tentar fechar o driver do eSAJ: {e_quit}")
        print("Script principal finalizado.")