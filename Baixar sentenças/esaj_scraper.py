# esaj_scraper.py
import os
import time
import traceback
import glob
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager  # pip install webdriver-manager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    JavascriptException,
    WebDriverException,
    ElementClickInterceptedException,
    ElementNotInteractableException
)

try:
    import config
except ImportError:
    print("ERRO CRÍTICO em esaj_scraper.py: O arquivo config.py não foi encontrado.")


    class ConfigFallback:
        URL_ESAJ_LOGIN_CAS = "https://esaj.tjsp.jus.br/sajcas/login?service=https%3A%2F%2Fesaj.tjsp.jus.br%2Fesaj%2Fportal.do%3Fservico%3D740000"
        PASTA_RAIZ_PROJETO = "."
        TIPOS_DOCUMENTO_DESEJADOS_ESAJ = ['petição', 'decisão', 'sentença', 'despacho']
        # Adiciona fallbacks para credenciais Yahoo se config.py não carregar
        YAHOO_EMAIL_ADDRESS = None
        YAHOO_APP_PASSWORD = None


    config = ConfigFallback()

# --- IMPORTAÇÃO DO LEITOR DE TOKEN DO YAHOO ---
try:
    from yahoo_token_reader import fetch_esaj_token_from_yahoo
except ImportError:
    print(
        "ERRO CRÍTICO em esaj_scraper.py: O arquivo yahoo_token_reader.py não foi encontrado ou não pôde ser importado.")


    # Define uma função de fallback para evitar crash se a importação falhar, mas a funcionalidade ficará comprometida.
    def fetch_esaj_token_from_yahoo(max_retries=1, retry_delay=1) -> Optional[str]:  # Adicionado Optional
        print("  [FallbackTokenReader] Função fetch_esaj_token_from_yahoo não disponível (import falhou).")
        return None


# --- FIM DA IMPORTAÇÃO ---


def configurar_chrome_options(download_path):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")
    prefs = {
        "download.default_directory": download_path,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "profile.default_content_settings.popups": 0,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36')
    return chrome_options


def wait_for_download_complete(download_dir, processo_numero_referencia, timeout=240):
    start_time = time.time()
    print(f"--- Esperando download para o processo '{processo_numero_referencia}' finalizar (até {timeout}s) ---")
    initial_files_pdf = set(glob.glob(os.path.join(download_dir, "*.pdf")))
    initial_files_zip = set(glob.glob(os.path.join(download_dir, "*.zip")))
    initial_files_all = initial_files_pdf.union(initial_files_zip)

    while time.time() - start_time < timeout:
        for f_crdownload in glob.glob(os.path.join(download_dir, "*.crdownload")):
            try:
                print(f"--> Removendo .crdownload ativo/antigo: {f_crdownload}")
                os.remove(f_crdownload)
            except Exception as e_remove:
                print(f"AVISO: Não removeu .crdownload {f_crdownload}: {e_remove}")

        current_files_pdf = set(glob.glob(os.path.join(download_dir, "*.pdf")))
        current_files_zip = set(glob.glob(os.path.join(download_dir, "*.zip")))
        current_files_all = current_files_pdf.union(current_files_zip)
        new_files = current_files_all - initial_files_all

        if new_files:
            potential_file = new_files.pop()
            print(f"--> Novo arquivo detectado: {os.path.basename(potential_file)}")
            initial_size = -1;
            stable_count = 0;
            check_time_file = time.time()
            while time.time() - check_time_file < 15 and stable_count < 4:
                try:
                    if not os.path.exists(potential_file):
                        print(f"----> Arquivo {os.path.basename(potential_file)} desapareceu.");
                        potential_file = None;
                        break
                    current_size = os.path.getsize(potential_file)
                    corresponding_crdownload = potential_file + ".crdownload"
                    if os.path.exists(corresponding_crdownload):
                        print(
                            f"----> {os.path.basename(corresponding_crdownload)} ainda existe. Download em andamento.")
                        stable_count = 0;
                        initial_size = -1;
                        time.sleep(2);
                        continue
                    if current_size == initial_size and current_size > 0:
                        stable_count += 1
                    else:
                        initial_size = current_size; stable_count = 0
                    print(
                        f"----> Checando {os.path.basename(potential_file)}: {current_size}b, estável: {stable_count}/4")
                    time.sleep(1)
                except FileNotFoundError:
                    print(
                        f"----> Arquivo {os.path.basename(potential_file)} desapareceu."); potential_file = None; break
                except Exception as e_size:
                    print(f"----> Erro tamanho {os.path.basename(potential_file)}: {e_size}"); time.sleep(
                        1); stable_count = 0

            if potential_file and stable_count >= 4:
                print(
                    f"--> Download de '{os.path.basename(potential_file)}' concluído e estável (tamanho: {initial_size}b).")
                return potential_file
            elif potential_file:
                print(
                    f"--> Arquivo {os.path.basename(potential_file)} não estabilizou ({stable_count}/4). Continuando a esperar...")
                initial_files_all.add(potential_file)

        active_crdownloads = glob.glob(os.path.join(download_dir, "*.crdownload"))
        if active_crdownloads:
            print(
                f"--> Download para '{processo_numero_referencia}' em andamento ({len(active_crdownloads)} .crdownload)...")
        elif not new_files:
            print(f"--> Nenhum novo arquivo ou download em andamento para '{processo_numero_referencia}'.")
        time.sleep(3)
    print(f"ERRO: Download para '{processo_numero_referencia}' não concluiu/estabilizou em {timeout}s.");
    return None


# --- FUNÇÃO LOGIN_ESAJ ATUALIZADA PARA USAR O YAHOO_TOKEN_READER ---
def login_esaj(driver, usuario, senha):
    """Realiza o login no eSAJ, buscando o token automaticamente do Yahoo Mail."""
    print(f"Navegando para: {config.URL_ESAJ_LOGIN_CAS}")
    driver.get(config.URL_ESAJ_LOGIN_CAS)

    print(f"Tentando login no eSAJ com usuário: {usuario}")
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, 'usernameForm'))).send_keys(usuario)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, 'passwordForm'))).send_keys(senha)
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, 'pbEntrar'))).click()
    print("Login inicial (usuário/senha) enviado. Aguardando campo do token ou página de token...")

    try:
        # Espera um pouco para a página de token carregar
        print("  Aguardando até 10s para a página de token do eSAJ carregar completamente...")
        time.sleep(10)  # Pausa para o eSAJ processar e enviar o email com o token

        campo_codigo_esaj = WebDriverWait(driver, 45).until(
            EC.visibility_of_element_located((By.ID, 'tokenInformado'))
        )
        print("  Campo do token encontrado e visível na página do eSAJ.")

        print("  Tentando buscar token automaticamente do Yahoo Mail...")
        # Chama a função para buscar o token no Yahoo
        # Aumentar retries e delay se o email do eSAJ demorar muito para chegar
        codigo_do_email = fetch_esaj_token_from_yahoo(max_retries=4, retry_delay=45)

        if codigo_do_email:
            print(f"  Token recuperado do email: {codigo_do_email}")
            campo_codigo_esaj.send_keys(codigo_do_email)
            WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, 'btnEnviarToken'))).click()
            print("  Token (do email) enviado ao eSAJ. Aguardando página pós-login...")
        else:
            print("  ERRO: Não foi possível recuperar o token do Yahoo Mail.")
            print("  Você pode tentar digitar manualmente se o campo ainda estiver visível.")
            # Fallback para input manual se a busca automática falhar
            try:
                if campo_codigo_esaj.is_displayed():  # Verifica se o campo ainda está lá
                    codigo_validacao_manual = input(
                        "!!! FALHA NA BUSCA AUTOMÁTICA. DIGITE O CÓDIGO DO E-MAIL DO ESAJ E PRESSIONE ENTER: ")
                    campo_codigo_esaj.send_keys(codigo_validacao_manual)
                    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, 'btnEnviarToken'))).click()
                    print("  Token (manual) enviado ao eSAJ. Aguardando página pós-login...")
                else:
                    print("  Campo do token não está mais visível para entrada manual.")
                    return False  # Falha no login
            except Exception as e_manual_token:
                print(f"  ERRO ao tentar inserir token manualmente: {e_manual_token}")
                return False  # Falha no login

    except TimeoutException:
        print("  ERRO: Campo do token (id='tokenInformado') não apareceu em 45 segundos após enviar usuário/senha.")
        if config.URL_ESAJ_LOGIN_CAS not in driver.current_url and "portal.do" in driver.current_url:
            print(
                "  AVISO: URL mudou, pode ter logado (ou o token foi automático/reutilizado). Prosseguindo com cautela...")
            # Se logou direto, não precisa de token, considera sucesso.
        else:
            print("  Verifique se o usuário/senha estão corretos ou se a página de login mudou.")
            driver.save_screenshot(os.path.join(config.PASTA_RAIZ_PROJETO, "debug_erro_campo_token.png"))
            return False
    except Exception as e_token_geral:
        print(f"  ERRO geral durante o processo de obtenção/envio do token: {e_token_geral}")
        traceback.print_exc()
        return False

    locator_link_consultas_processuais = (By.XPATH,
                                          "//a[contains(text(), 'Consultas Processuais') and contains(@href, 'servico=190090')]")
    try:
        WebDriverWait(driver, 40).until(EC.element_to_be_clickable(locator_link_consultas_processuais))
        print("Login completo no eSAJ bem sucedido!")
        return True
    except Exception as e_post_login:
        print(
            f"ERRO PÓS-LOGIN (após tentativa de token): Link 'Consultas Processuais' não encontrado. Erro: {e_post_login}")
        current_url = driver.current_url;
        print(f"URL atual: {current_url}")
        if "login" in current_url.lower() or "sajcas" in current_url.lower():
            print("Ainda na página de login ou CAS, o login provavelmente falhou (usuário/senha/token incorretos?).")
        driver.save_screenshot(os.path.join(config.PASTA_RAIZ_PROJETO, "debug_login_final_error.png"))
        return False


# ... (o resto do arquivo esaj_scraper.py: navigate_to_process_search_page, wait_for_overlay_to_disappear, download_selected_documents_from_esaj permanecem como na última versão completa que te enviei) ...
# Certifique-se de que essas funções estejam presentes e corretas conforme a última versão funcional.
# Vou colar elas aqui novamente para garantir.

def navigate_to_process_search_page(driver, main_window_handle, max_attempts=3):
    locator_consultas = (By.XPATH,
                         "//a[contains(text(), 'Consultas Processuais') and contains(@href, 'servico=190090')]")
    locator_1grau = (By.XPATH,
                     "//a[contains(text(), 'Consulta de Processos do 1ºGrau') and @href='https://esaj.tjsp.jus.br/cpopg/open.do']")
    for attempt in range(max_attempts):
        try:
            if main_window_handle and main_window_handle in driver.window_handles:
                if driver.current_window_handle != main_window_handle: driver.switch_to.window(main_window_handle)
            elif driver.window_handles:
                print("AVISO: Janela principal perdida, focando na primeira."); driver.switch_to.window(
                    driver.window_handles[0]); main_window_handle = driver.current_window_handle
            else:
                raise WebDriverException("Nenhuma janela disponível.")
            print(f"Tentativa {attempt + 1} de ir para busca...");
            WebDriverWait(driver, 20).until(EC.element_to_be_clickable(locator_consultas)).click();
            print(f"  Clicado em 'Consultas Processuais'.")
            WebDriverWait(driver, 20).until(EC.element_to_be_clickable(locator_1grau)).click();
            print(f"  Clicado em 'Consulta de Processos do 1ºGrau'.")
            WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.ID, 'numeroDigitoAnoUnificado')));
            print(f"  Página de busca carregada.");
            return True
        except Exception as e:
            print(f"AVISO: Falha ao ir para busca (tentativa {attempt + 1}/{max_attempts}): {e}")
            try:
                print("  Retornando ao portal...");
                driver.get('https://esaj.tjsp.jus.br/esaj/portal.do?servico=740000')
                WebDriverWait(driver, 20).until(EC.element_to_be_clickable(locator_consultas));
                time.sleep(3)
            except Exception as get_e:
                print(f"AVISO: Falha ao retornar ao portal: {get_e}");
            if attempt == max_attempts - 1: return False
    print("ERRO: Não foi para página de busca.");
    return False


def wait_for_overlay_to_disappear(driver, timeout=45):
    overlay_locator = (By.CSS_SELECTOR, "div.blockUI.blockOverlay, div.blockUI.blockPage")
    try:
        print("    Aguardando possível overlay 'blockUI' desaparecer (max %ss)..." % timeout)
        WebDriverWait(driver, timeout).until(EC.invisibility_of_element_located(overlay_locator))
        print("    Overlay 'blockUI' não está mais visível (ou não foi encontrado inicialmente).")
        return True
    except TimeoutException:
        print(f"    AVISO: Overlay 'blockUI' ainda presente após {timeout}s. Tentando remover via JS.")
        try:
            if driver.find_elements(*overlay_locator):
                driver.execute_script(
                    "var elements = document.querySelectorAll('div.blockUI.blockOverlay, div.blockUI.blockPage'); elements.forEach(function(e){ e.style.display='none'; });")
                print("    Overlays 'blockUI' tiveram display setado para 'none' via JS.");
                time.sleep(0.5);
                return True
        except Exception as e_js_remove:
            print(f"    AVISO: Falha ao tentar remover overlay via JS: {e_js_remove}")
        return False
    except Exception as e_overlay_gen:
        print(f"    AVISO: Erro ao esperar overlay desaparecer: {e_overlay_gen}"); return True


def download_selected_documents_from_esaj(driver, numero_processo_completo_original, download_folder,
                                          tipos_documento_desejados):
    numero_processo_cnj_numeros_para_busca = ''.join(filter(str.isdigit, numero_processo_completo_original))
    print(
        f"\n--- Processando eSAJ para Processo Planilha: {numero_processo_completo_original} (CNJ Num Limpo para busca: {numero_processo_cnj_numeros_para_busca}) ---")
    main_window_handle = driver.current_window_handle
    pasta_digital_window_handle = None;
    caminho_arquivo_baixado_final = None

    locator_num_principal = (By.ID, 'numeroDigitoAnoUnificado')
    if not (driver.current_url.startswith("https://esaj.tjsp.jus.br/cpopg/open.do") and driver.find_elements(
            *locator_num_principal)):
        if not navigate_to_process_search_page(driver, main_window_handle): print(
            f"ERRO CRÍTICO: Não navegou para busca para {numero_processo_cnj_numeros_para_busca}."); return None

    WebDriverWait(driver, 15).until(EC.presence_of_element_located(locator_num_principal)).clear()
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, 'foroNumeroUnificado'))).clear()
    time.sleep(0.3)
    if len(numero_processo_cnj_numeros_para_busca) >= 20:
        driver.find_element(*locator_num_principal).send_keys(
            f"{numero_processo_cnj_numeros_para_busca[0:7]}-{numero_processo_cnj_numeros_para_busca[7:9]}.{numero_processo_cnj_numeros_para_busca[9:13]}")
        driver.find_element(By.ID, 'foroNumeroUnificado').send_keys(numero_processo_cnj_numeros_para_busca[-4:])
        time.sleep(0.5)
    else:
        print(f"ERRO: Formato CNJ '{numero_processo_cnj_numeros_para_busca}' inválido. Pulando."); return None
    WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, 'botaoConsultarProcessos'))).click()
    print("  Pesquisa enviada. Aguardando resultados...")

    loc_link_autos = (By.ID, 'linkPasta')
    loc_proc_nao_enc = (By.XPATH,
                        "//div[contains(@class, 'mensagemRetorno') and (contains(.,'Processo não encontrado') or contains(.,'processo em segredo de justiça') or contains(.,'O tipo de pesquisa informado é inválido'))]")
    try:
        WebDriverWait(driver, 30).until(
            EC.any_of(EC.element_to_be_clickable(loc_link_autos), EC.presence_of_element_located(loc_proc_nao_enc)))
    except TimeoutException:
        print(f"  ERRO: Timeout resultado pesquisa {numero_processo_cnj_numeros_para_busca}."); driver.save_screenshot(
            os.path.join(config.PASTA_RAIZ_PROJETO,
                         f"debug_timeout_pesquisa_{numero_processo_cnj_numeros_para_busca}.png")); return None
    if driver.find_elements(*loc_proc_nao_enc): print(
        f"  ATENÇÃO: Processo {numero_processo_cnj_numeros_para_busca} não encontrado/sigiloso/inválido."); return None

    initial_handles_count = len(driver.window_handles)
    print(
        f"  [DEBUG] Número de janelas/abas ANTES de 'Visualizar Autos': {initial_handles_count}, URL: {driver.current_url}")
    try:
        link_visualizar_autos_el = WebDriverWait(driver, 20).until(EC.element_to_be_clickable(loc_link_autos))
        driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", link_visualizar_autos_el)
        print("  'Visualizar autos' clicado (via JS).")
    except Exception as e_click_autos:
        print(f"  ERRO ao tentar clicar em 'Visualizar autos': {e_click_autos}."); driver.save_screenshot(
            os.path.join(config.PASTA_RAIZ_PROJETO,
                         f"debug_erro_clique_autos_{numero_processo_cnj_numeros_para_busca}.png")); return None

    timeout_nova_janela = 90
    print(f"  Aguardando nova janela/aba da pasta digital abrir (até {timeout_nova_janela}s)...")
    try:
        WebDriverWait(driver, timeout_nova_janela).until(EC.number_of_windows_to_be(initial_handles_count + 1))
        new_window_handle = \
        [handle for handle in driver.window_handles if handle not in driver.window_handles[:initial_handles_count]][0]
        pasta_digital_window_handle = new_window_handle
        driver.switch_to.window(pasta_digital_window_handle)
        print(f"  Foco na NOVA aba/janela Autos Digitais: {pasta_digital_window_handle}, URL: {driver.current_url}")
    except TimeoutException:
        print(
            f"  ERRO: Timeout ({timeout_nova_janela}s) - Nova janela/aba da pasta digital NÃO ABRIU ou não foi detectada.")
        driver.save_screenshot(os.path.join(config.PASTA_RAIZ_PROJETO,
                                            f"debug_timeout_nova_janela_{numero_processo_cnj_numeros_para_busca}.png"));
        return None

    try:
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.ID, 'toggleArvoreButton')));
        print("  Página de Autos Digitais carregada.")
        wait_for_overlay_to_disappear(driver, 45)

        print("  --- Iniciando seleção seletiva de documentos ---")
        documentos_selecionados_count = 0
        WebDriverWait(driver, 45).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "jstree-anchor")))
        time.sleep(3)
        ancoras_documentos = driver.find_elements(By.CLASS_NAME, "jstree-anchor")
        print(f"    Encontrados {len(ancoras_documentos)} elementos 'jstree-anchor'.")

        for anchor_idx, anchor in enumerate(ancoras_documentos):
            try:
                driver.execute_script("arguments[0].scrollIntoViewIfNeeded({block: 'center', inline: 'nearest'});",
                                      anchor);
                time.sleep(0.2)
                texto_doc_bruto = anchor.text
                if not texto_doc_bruto: continue
                texto_doc_norm = texto_doc_bruto.strip().lower()
                for tipo_desejado in config.TIPOS_DOCUMENTO_DESEJADOS_ESAJ:
                    if tipo_desejado in texto_doc_norm:
                        print(
                            f"      >> Documento tipo '{tipo_desejado}' ({texto_doc_bruto[:50]}...). Tentando selecionar.")
                        checkbox_clicado = False
                        try:
                            cb = anchor.find_element(By.XPATH,
                                                     "./preceding-sibling::i[contains(@class, 'jstree-checkbox')][1]")
                            if cb.is_displayed() and cb.is_enabled():
                                driver.execute_script("arguments[0].click();", cb);
                                print(f"        Checkbox (irmão <a>) clicado via JS.");
                                checkbox_clicado = True
                        except NoSuchElementException:
                            try:
                                cb = anchor.find_element(By.XPATH, "./i[contains(@class, 'jstree-checkbox')]")
                                if cb.is_displayed() and cb.is_enabled():
                                    driver.execute_script("arguments[0].click();", cb);
                                    print(f"        Checkbox (dentro <a>) clicado via JS.");
                                    checkbox_clicado = True
                            except NoSuchElementException:
                                print(f"        !! ERRO: Checkbox não encontrado para '{texto_doc_bruto[:50]}...'")
                            except Exception as e_cb_click:
                                print(f"        !! ERRO ao clicar checkbox (dentro): {e_cb_click}")
                        except Exception as e_cb_click:
                            print(f"        !! ERRO ao clicar checkbox (irmão): {e_cb_click}")
                        if checkbox_clicado: documentos_selecionados_count += 1; time.sleep(0.3); break
            except StaleElementReferenceException:
                print("    AVISO: Âncora 'stale'. Interrompendo seleção."); break
            except Exception as e_anchor:
                print(f"    AVISO: Erro processando âncora ('{getattr(anchor, 'text', 'N/A')[:50]}...'): {e_anchor}")

        print(f"  --- Seleção concluída. {documentos_selecionados_count} cliques tentados. ---")
        if documentos_selecionados_count == 0: print(
            "  AVISO: Nenhum doc. selecionado. Download pode falhar/vir vazio."); return None

        time.sleep(2)
        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, 'salvarButton'))).click();
        print("  Botão 'Versão para impressão' clicado.")

        try:
            msg_sel_item_loc = (By.XPATH,
                                "//div[@id='mensagemAlert' and contains(text(), 'Selecione pelo menos um item da árvore.')]")
            WebDriverWait(driver, 7).until(EC.visibility_of_element_located(msg_sel_item_loc));
            print("  ALERTA: Modal 'Selecione pelo menos um item' detectado!")
            btn_ok_aviso_loc = (By.XPATH,
                                "//div[contains(@class, 'popup-modal-div-all')]//input[@type='button' and @value='Ok']")
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(btn_ok_aviso_loc)).click();
            print("    Botão 'Ok' do modal de aviso clicado.");
            return None
        except TimeoutException:
            print("    Modal 'Selecione pelo menos um item' não detectado. OK."); pass

        loc_radio1 = (By.ID, 'opcao1');
        loc_btn_cont1 = (By.ID, 'botaoContinuar')
        try:
            print("    Esperando opção 'Arquivo único'...");
            el_radio1 = WebDriverWait(driver, 20).until(EC.element_to_be_clickable(loc_radio1))
            if not el_radio1.is_selected():
                driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", el_radio1); print(
                    "    Opção 'Arquivo único' clicada.")
            else:
                print("    Opção 'Arquivo único' já selecionada.")
            time.sleep(0.5)
        except Exception as e_r1:
            print(f"    AVISO: Interação com 'Arquivo único' falhou: {e_r1}")

        try:
            print("    Esperando botão 'Continuar' (modal 1)...");
            el_btn_cont1 = WebDriverWait(driver, 25).until(EC.element_to_be_clickable(loc_btn_cont1))
            driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", el_btn_cont1);
            print("    Botão 'Continuar' (modal 1) clicado via JS.");
            time.sleep(35)
        except Exception as e_js_c1:
            print(f"    ERRO JS ao clicar 'Continuar' (modal 1): {e_js_c1}")
            try:
                print("    Tentando clique direto 'Continuar' (modal 1)...")
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable(loc_btn_cont1)).click();
                print("    Botão 'Continuar' (modal 1) clicado (direto).");
                time.sleep(35)
            except Exception as e_dir_c1:
                print(f"    ERRO clique direto 'Continuar' (modal 1) falhou: {e_dir_c1}"); raise

        loc_btn_salvar2 = (By.ID, 'btnDownloadDocumento')
        print("    Esperando botão 'Salvar o documento' (modal 2)...");
        time.sleep(2)
        el_btn_salvar2 = WebDriverWait(driver, 150).until(EC.element_to_be_clickable(loc_btn_salvar2));
        print("    Botão 'Salvar o documento' (modal 2) está clicável.")
        driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", el_btn_salvar2);
        print("    Clique 'Salvar o documento' (modal 2) executado via JS.")

        caminho_arquivo_baixado_final = wait_for_download_complete(download_folder, numero_processo_completo_original,
                                                                   timeout=300)

    except TimeoutException as e_timeout_pd:
        print(
            f"  ERRO TIMEOUT na Pasta Digital {numero_processo_cnj_numeros_para_busca}: {e_timeout_pd}"); driver.save_screenshot(
            os.path.join(config.PASTA_RAIZ_PROJETO,
                         f"debug_timeout_pasta_{numero_processo_cnj_numeros_para_busca}.png"))
    except StaleElementReferenceException:
        print(
            f"  ERRO STALE ELEMENT na Pasta Digital {numero_processo_cnj_numeros_para_busca}. Será tentado na próxima execução se não logado.")
    except Exception as e_geral_pd:
        print(
            f"  ERRO INESPERADO na Pasta Digital {numero_processo_cnj_numeros_para_busca}: {e_geral_pd}"); traceback.print_exc(); driver.save_screenshot(
            os.path.join(config.PASTA_RAIZ_PROJETO, f"debug_erro_pasta_{numero_processo_cnj_numeros_para_busca}.png"))
    finally:
        if pasta_digital_window_handle and pasta_digital_window_handle in driver.window_handles:
            if driver.current_window_handle == pasta_digital_window_handle:
                try:
                    print(f"  Fechando aba/janela Autos Digitais: {pasta_digital_window_handle}"); driver.close()
                except WebDriverException as e_close:
                    print(f"  AVISO: Erro ao fechar aba pasta digital: {e_close}")
        current_handles_after = driver.window_handles
        if main_window_handle and main_window_handle in current_handles_after:
            driver.switch_to.window(main_window_handle)
        elif current_handles_after:
            print("  AVISO: Focando primeira janela pós-pasta digital."); driver.switch_to.window(
                current_handles_after[0])

    return caminho_arquivo_baixado_final