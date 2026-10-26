import json
import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright

# Carrega arquivo .env se existir
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

BASE_URL = "https://affiliate.tiktok.com/affiliate/creator?shop_region=BR&shop_id=7494973971254576251"
PROFILE_DIR = os.path.abspath("./chrome_profile")
STORAGE_STATE_FILE = os.path.abspath("./storage_state.json")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ALLOWED_CHAT_ID = os.getenv("ALLOWED_CHAT_ID", "")


def get_browser_context(p, headless=False):
    kwargs = {
        "user_data_dir": PROFILE_DIR,
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions",
            "--disable-background-networking",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
        "viewport": {"width": 1600, "height": 900},
    }
    ctx = None
    for ch in ("msedge", "chrome", None):
        try:
            ctx = p.chromium.launch_persistent_context(**(kwargs | ({"channel": ch} if ch else {})))
            break
        except Exception:
            continue
    if not ctx:
        raise RuntimeError("Não foi possível iniciar o navegador.")

    # Carrega cookies da variável TIKTOK_COOKIES (GitHub Secrets) ou do storage_state.json
    cookies_json = os.getenv("TIKTOK_COOKIES", "")
    if cookies_json:
        try:
            state = json.loads(cookies_json)
            ctx.add_cookies(state.get("cookies", state if isinstance(state, list) else []))
        except Exception as e:
            print(f"[!] Aviso ao carregar TIKTOK_COOKIES: {e}")
    elif os.path.exists(STORAGE_STATE_FILE):
        try:
            with open(STORAGE_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                ctx.add_cookies(state.get("cookies", []))
        except Exception as e:
            print(f"[!] Aviso ao carregar storage_state.json: {e}")

    return ctx


def export_cookies():
    with sync_playwright() as p:
        context = get_browser_context(p, headless=False)
        context.storage_state(path=STORAGE_STATE_FILE)
        context.close()
    print(f"[+] Sessão exportada com sucesso em: {STORAGE_STATE_FILE}")


def manual_login():
    print(f"[*] Abrindo navegador para login manual. Perfil salvo em: {PROFILE_DIR}")
    with sync_playwright() as p:
        context = get_browser_context(p, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(BASE_URL, wait_until="domcontentloaded")
        print("[!] Faça login no TikTok Shop no navegador aberto.")
        print("[!] Quando terminar de logar e carregar o painel, pressione ENTER aqui no terminal...")
        input()
        context.storage_state(path=STORAGE_STATE_FILE)
        context.close()
    print(f"[+] Login concluído e sessão salva em {PROFILE_DIR} e {STORAGE_STATE_FILE}!")


def capture_with_context(context, creator_name):
    t0 = time.perf_counter()
    creator_clean = creator_name.strip().lstrip("@")
    print(f"[*] Buscando criador: {creator_clean}")

    page = context.pages[0] if context.pages else context.new_page()
    for extra in context.pages[1:]:
        try:
            extra.close()
        except Exception:
            pass

    if "affiliate/creator" not in page.url or "creator/detail" in page.url:
        page.goto(BASE_URL, wait_until="domcontentloaded")

    search_box = page.locator(
        "input[placeholder*='Pesquisar'], input[placeholder*='Search'], input[type='search'], input.arco-input"
    ).first
    search_box.wait_for(state="visible", timeout=20000)

    search_box.click()
    search_box.fill("")
    search_box.fill(creator_clean)
    search_box.press("Enter")
    print(f"[*] Pesquisa enviada ({time.perf_counter() - t0:.1f}s), aguardando criador na tabela...")

    try:
        page.locator("text=Resultados da pesquisa, text=Encontrar criadores").first.click(timeout=2000)
    except Exception:
        pass

    row_name = page.locator("tbody").get_by_text(creator_clean, exact=False).first
    row_name.wait_for(state="visible", timeout=15000)

    detail_page = None
    for attempt in range(2):
        try:
            with context.expect_page(timeout=6000) as new_page_info:
                row_name.click(force=(attempt > 0))
            detail_page = new_page_info.value
            break
        except Exception:
            if len(context.pages) > 1:
                detail_page = context.pages[-1]
                break
            time.sleep(0.5)

    if not detail_page:
        raise RuntimeError(f"Não foi possível abrir a página de detalhes de '{creator_clean}'.")

    detail_page.bring_to_front()
    detail_page.wait_for_load_state("domcontentloaded")

    # Aguarda a página carregar (tenta Detalhes do criador ou Categorias com fallback)
    try:
        detail_page.locator("text=Detalhes do criador, text=Creator details, text=Categorias, text=Categories").first.wait_for(state="visible", timeout=25000)
    except Exception:
        print("[!] Aviso: cabeçalho demorou a aparecer, prosseguindo com captura...")
    time.sleep(1)

    cat_label = detail_page.locator("text=Categorias, text=Categories").first
    try:
        cat_label.wait_for(state="visible", timeout=10000)
        detail_page.locator("text=Valor Bruto da Mercadoria (GMV), text=GMV").first.wait_for(state="visible", timeout=10000)
        detail_page.locator("canvas, svg").nth(3).wait_for(state="visible", timeout=6000)
    except Exception:
        pass
    time.sleep(0.5)

    # Print 2: Hover no valor ao lado de 'Categorias'
    print(f"[*] Fazendo hover em 'Categorias' ({time.perf_counter() - t0:.1f}s)...")
    cat_value = cat_label.locator("xpath=following-sibling::*[1]")
    if cat_value.count() > 0 and cat_value.first.is_visible():
        inner_target = cat_value.locator("*").first
        if inner_target.count() > 0 and inner_target.is_visible():
            inner_target.hover()
        else:
            cat_value.first.hover()
    else:
        box = cat_label.bounding_box()
        if box:
            detail_page.mouse.move(box["x"] + box["width"] + 50, box["y"] + box["height"] / 2)

    try:
        detail_page.locator("text=Categoria do produto:, text=Product category:").first.wait_for(state="visible", timeout=1500)
        time.sleep(0.15)
    except Exception:
        time.sleep(0.3)

    print2_path = os.path.abspath(f"print2_hover_{creator_clean}.png")
    detail_page.screenshot(path=print2_path)
    print(f"[+] Print 2 salvo ({time.perf_counter() - t0:.1f}s): {print2_path}")

    # Remove o hover/balão preto para o Print 1 mostrar a tela normal (incluindo Classificação/avaliações)
    detail_page.mouse.move(10, 10)
    detail_page.evaluate("""() => {
        document.querySelectorAll('.arco-tooltip-popup, [role="tooltip"]').forEach(el => el.remove());
        window.scrollTo(0, document.body.scrollHeight);
        document.querySelectorAll('*').forEach(el => {
            const style = window.getComputedStyle(el);
            if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
                el.style.overflow = 'visible';
                el.style.maxHeight = 'none';
                el.style.height = 'auto';
            }
        });
    }""")

    try:
        detail_page.locator("text=Tendências, text=TRENDS").first.wait_for(state="visible", timeout=4000)
    except Exception:
        pass
    time.sleep(0.6)
    detail_page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.2)

    print1_path = os.path.abspath(f"print1_full_{creator_clean}.png")
    detail_page.screenshot(path=print1_path, full_page=True)
    detail_page.close()

    elapsed = time.perf_counter() - t0
    print(f"[+] Print 1 salvo ({elapsed:.1f}s total): {print1_path}")
    return print1_path, print2_path


def capture_creator(creator_name):
    with sync_playwright() as p:
        context = get_browser_context(p, headless=False)
        try:
            return capture_with_context(context, creator_name)
        finally:
            context.close()


def send_telegram(session, chat_id, print1_path, print2_path, caption=""):
    api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    with open(print1_path, "rb") as f1:
        session.post(
            f"{api}/sendDocument",
            data={"chat_id": chat_id, "caption": f"📄 Página Inteira: {caption}"},
            files={"document": f1},
        )
    with open(print2_path, "rb") as f2:
        session.post(
            f"{api}/sendPhoto",
            data={"chat_id": chat_id, "caption": f"🔍 Categorias Hover: {caption}"},
            files={"photo": f2},
        )


def process_pending_updates():
    """Modo GitHub Actions: processa todas as mensagens pendentes na fila do Telegram e encerra (ou escuta pelo tempo definido em LISTEN_SECONDS)."""
    if not TELEGRAM_TOKEN:
        print("[!] Erro: TELEGRAM_TOKEN não configurado.")
        return

    listen_minutes = float(os.getenv("LISTEN_MINUTES", "0") or "0")
    listen_seconds = int(listen_minutes * 60) if listen_minutes > 0 else int(os.getenv("LISTEN_SECONDS", "45"))
    start_time = time.time()
    session = requests.Session()
    api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    offset = 0
    context = None

    with sync_playwright() as p:
        while True:
            try:
                res = session.get(f"{api}/getUpdates", params={"offset": offset, "timeout": 10 if listen_seconds > 0 else 2}).json()
                updates = res.get("result", [])

                for update in updates:
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "").strip()

                    if not text or (ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID):
                        continue

                    if text.lower().startswith("/start"):
                        session.post(
                            f"{api}/sendMessage",
                            data={"chat_id": chat_id, "text": "Envie o @ ou nome do criador para analisar."},
                        )
                        continue

                    t_req = time.perf_counter()
                    session.post(
                        f"{api}/sendMessage",
                        data={"chat_id": chat_id, "text": f"⏳ Analisando perfil na nuvem: {text}..."},
                    )
                    try:
                        if context is None:
                            context = get_browser_context(p, headless=False)
                        p1, p2 = capture_with_context(context, text)
                        send_telegram(session, chat_id, p1, p2, caption=f"{text} ({time.perf_counter() - t_req:.1f}s)")
                    except Exception as e:
                        session.post(
                            f"{api}/sendMessage",
                            data={"chat_id": chat_id, "text": f"❌ Erro ao capturar: {e}"},
                        )
                    finally:
                        # Confirma leitura do update no Telegram para não repetir na próxima execução
                        session.get(f"{api}/getUpdates", params={"offset": offset, "timeout": 1})

                if listen_seconds <= 0 or (time.time() - start_time) >= listen_seconds:
                    break
            except Exception as e:
                print(f"[!] Erro no loop: {e}")
                if listen_seconds <= 0:
                    break
                time.sleep(2)

        if context:
            context.close()


def run_bot():
    if not TELEGRAM_TOKEN:
        print("[!] Erro: Defina a variável TELEGRAM_TOKEN no ambiente ou no arquivo .env.")
        return

    print("[*] Iniciando navegador persistente para respostas instantâneas no Telegram...")
    session = requests.Session()
    api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    offset = 0

    with sync_playwright() as p:
        context = get_browser_context(p, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(BASE_URL, wait_until="domcontentloaded")
        print("[+] Navegador pronto! Bot Telegram escutando mensagens...")

        while True:
            try:
                res = session.get(f"{api}/getUpdates", params={"offset": offset, "timeout": 30}).json()
                for update in res.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "").strip()

                    if not text or (ALLOWED_CHAT_ID and chat_id != ALLOWED_CHAT_ID):
                        continue

                    if text.lower().startswith("/start"):
                        session.post(
                            f"{api}/sendMessage",
                            data={"chat_id": chat_id, "text": "Envie o @ ou nome do criador para analisar."},
                        )
                        continue

                    t_req = time.perf_counter()
                    session.post(
                        f"{api}/sendMessage",
                        data={"chat_id": chat_id, "text": f"⏳ Analisando perfil: {text}..."},
                    )
                    try:
                        p1, p2 = capture_with_context(context, text)
                        send_telegram(session, chat_id, p1, p2, caption=f"{text} ({time.perf_counter() - t_req:.1f}s)")
                    except Exception as e:
                        session.post(
                            f"{api}/sendMessage",
                            data={"chat_id": chat_id, "text": f"❌ Erro ao capturar: {e}"},
                        )
            except KeyboardInterrupt:
                break
            except Exception:
                time.sleep(2)


if __name__ == "__main__":
    if "--login" in sys.argv:
        manual_login()
    elif "--export-cookies" in sys.argv:
        export_cookies()
    elif "--once" in sys.argv:
        process_pending_updates()
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        capture_creator(sys.argv[1])
    else:
        run_bot()
