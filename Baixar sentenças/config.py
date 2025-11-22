# config.py
import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env para o ambiente
load_dotenv()

# --- Configurações do Web Scraping eSAJ ---
URL_ESAJ_LOGIN_CAS = os.getenv(
    "URL_ESAJ_LOGIN_CAS",
    'https://esaj.tjsp.jus.br/sajcas/login?service=https%3A%2F%2Fesaj.tjsp.jus.br%2Fesaj%2Fportal.do%3Fservico%3D740000'
)
# É ALTAMENTE RECOMENDADO colocar usuário e senha do eSAJ no arquivo .env
ESAJ_USER = os.getenv("ESAJ_USER", "SEU_USUARIO_ESAJ_AQUI")  # Ex: ''
ESAJ_PASS = os.getenv("ESAJ_PASS", "SUA_SENHA_ESAJ_AQUI")    # Ex: ''

# --- Configurações para Ler o Token do Yahoo Mail ---
YAHOO_EMAIL_ADDRESS = os.getenv("YAHOO_EMAIL_ADDRESS")
YAHOO_APP_PASSWORD = os.getenv("YAHOO_APP_PASSWORD") # A senha de aplicativo de 16 caracteres
YAHOO_IMAP_SERVER = os.getenv("YAHOO_IMAP_SERVER", "imap.mail.yahoo.com")
YAHOO_IMAP_PORT_STR = os.getenv("YAHOO_IMAP_PORT", "993")

if YAHOO_IMAP_PORT_STR and YAHOO_IMAP_PORT_STR.isdigit():
    YAHOO_IMAP_PORT = int(YAHOO_IMAP_PORT_STR)
else:
    print(f"AVISO: YAHOO_IMAP_PORT ('{YAHOO_IMAP_PORT_STR}') inválido ou não encontrado no .env. Usando porta padrão 993.")
    YAHOO_IMAP_PORT = 993

# Verificação se as credenciais essenciais do Yahoo foram carregadas
if not YAHOO_EMAIL_ADDRESS or not YAHOO_APP_PASSWORD:
    print("AVISO: Credenciais do Yahoo Mail (YAHOO_EMAIL_ADDRESS, YAHOO_APP_PASSWORD) não totalmente configuradas no .env.")
    print("A leitura automática do token do eSAJ pode falhar se precisar dessas credenciais.")
if ESAJ_USER == "SEU_USUARIO_ESAJ_AQUI" or ESAJ_PASS == "SUA_SENHA_ESAJ_AQUI":
     print("AVISO: Credenciais do eSAJ (ESAJ_USER, ESAJ_PASS) não parecem estar configuradas no .env ou no config.py.")

# --- Configurações de Pastas ---
# Defina uma pasta raiz para o projeto. Todos os outros caminhos podem ser relativos a ela.
PASTA_RAIZ_PROJETO = os.getenv("PASTA_RAIZ_PROJETO", r'C:\Users\Priscila\APSDJ')
PASTA_DOWNLOAD_ESAJ = os.getenv("PASTA_DOWNLOAD_ESAJ", os.path.join(PASTA_RAIZ_PROJETO, 'ProcessosBaixadosTemp'))

# --- Configuração da Planilha de Processos para Baixar do eSAJ ---
NOME_ARQUIVO_PLANILHA_PROCESSOS_ESAJ = os.getenv("NOME_ARQUIVO_PLANILHA_PROCESSOS_ESAJ", 'PLANILHA EXCEL.xls')
CAMINHO_PLANILHA_PROCESSOS_ESAJ = os.path.join(PASTA_RAIZ_PROJETO, NOME_ARQUIVO_PLANILHA_PROCESSOS_ESAJ)
NOME_DA_ABA_EXCEL_PROCESSOS_ESAJ = os.getenv("NOME_DA_ABA_EXCEL_PROCESSOS_ESAJ", 'Worksheet')

# Palavras-chave para encontrar a coluna com os números dos processos na planilha
# Se estiver no .env, deve ser uma string separada por vírgulas: "palavra1,palavra2,palavra3"
PALAVRAS_CHAVE_COLUNA_PROCESSO_ESAJ_STR = os.getenv(
    "PALAVRAS_CHAVE_COLUNA_PROCESSO_ESAJ",
    'processo judicial,acao judicial,ACAO JUDICIAL,numero da acao,numero do processo,processo'
)
PALAVRAS_CHAVE_COLUNA_PROCESSO_ESAJ = [palavra.strip() for palavra in PALAVRAS_CHAVE_COLUNA_PROCESSO_ESAJ_STR.split(',')]

# --- Tipos de Documento para Baixar do ESAJ ---
# Se estiver no .env, deve ser uma string separada por vírgulas: "tipo1,tipo2,tipo3"
TIPOS_DOCUMENTO_DESEJADOS_ESAJ_STR = os.getenv(
    "TIPOS_DOCUMENTO_DESEJADOS_ESAJ",
    'petição,peticao,decisão,decisao,sentença,sentenca,despacho'
)
TIPOS_DOCUMENTO_DESEJADOS_ESAJ = [tipo.strip().lower() for tipo in TIPOS_DOCUMENTO_DESEJADOS_ESAJ_STR.split(',')]

# --- Log de Processos eSAJ Baixados ---
ARQUIVO_LOG_ESAJ_PROCESSADOS = os.getenv(
    "ARQUIVO_LOG_ESAJ_PROCESSADOS",
    os.path.join(PASTA_RAIZ_PROJETO, 'esaj_processos_baixados_log.txt')
)

# Opcional: Imprimir algumas configurações carregadas para depuração ao iniciar o main.py
# print(f"DEBUG config.py: Usuário eSAJ: {ESAJ_USER}")
# print(f"DEBUG config.py: Email Yahoo: {YAHOO_EMAIL_ADDRESS}")
# print(f"DEBUG config.py: Pasta Download eSAJ: {PASTA_DOWNLOAD_ESAJ}")
# print(f"DEBUG config.py: Planilha Processos eSAJ: {CAMINHO_PLANILHA_PROCESSOS_ESAJ}")

# print(f"DEBUG config.py: Tipos de Documento eSAJ: {TIPOS_DOCUMENTO_DESEJADOS_ESAJ}")
