#!/usr/bin/env python3
"""whatsapp_web.py — envia mensagens via WhatsApp Web (Selenium), 100% gratuito.

Primeira execução: abre o Chrome e mostra o QR code — escaneie uma vez com o
celular (WhatsApp > Aparelhos conectados). A sessão fica salva em
./whatsapp_profile/ (no .gitignore), então nas próximas execuções já entra
logado, sem pedir QR de novo.

O Chrome fica aberto durante todo o processo (não abre/fecha a cada envio) —
mais rápido e evita deslogar o WhatsApp Web por reconexões repetidas. Como o
Selenium fala com o navegador via WebDriver (não simula tecla física na tela),
não rouba o foco do seu mouse/teclado a cada envio.
"""

import pathlib
import time
import urllib.parse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROFILE_DIR = SCRIPT_DIR / "whatsapp_profile"

LOGGED_IN_XPATH = '//div[@id="pane-side"]'
MESSAGE_BOX_XPATH = '//footer//div[@contenteditable="true"]'

_driver = None


def _build_driver():
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    # WhatsApp Web derruba a sessão se detectar automação headless — sempre com janela visível.
    driver = webdriver.Chrome(options=options)
    driver.get("https://web.whatsapp.com")
    return driver


def _wait_login(driver, timeout=180):
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, LOGGED_IN_XPATH)))
        return
    except TimeoutException:
        pass
    print("📱 Escaneie o QR code no WhatsApp Web (aguardando login, até 3 min)...")
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, LOGGED_IN_XPATH)))
    print("✅ WhatsApp Web logado.")


def get_driver():
    """Reaproveita o Chrome já aberto; cria na primeira chamada."""
    global _driver
    if _driver is None:
        _driver = _build_driver()
        _wait_login(_driver)
    return _driver


def send_whatsapp_web(phone_e164, text, timeout=30):
    """Envia `text` pro número `phone_e164` (só dígitos, com DDI, ex: 5585981743866)
    via WhatsApp Web. Retorna True/False."""
    driver = get_driver()
    url = f"https://web.whatsapp.com/send?phone={phone_e164}&text={urllib.parse.quote(text)}"
    driver.get(url)

    try:
        box = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, MESSAGE_BOX_XPATH))
        )
    except TimeoutException:
        print(f"❌ WhatsApp Web: não carregou o chat pra {phone_e164} (número inválido/sem WhatsApp?)")
        return False

    time.sleep(2)  # tempo pro texto do ?text= pré-carregar no campo antes de enviar
    try:
        box.click()
        box.send_keys(Keys.ENTER)
    except Exception as exc:
        print(f"❌ WhatsApp Web: erro ao enviar pra {phone_e164}: {exc}")
        return False

    time.sleep(1)
    return True


def close_driver():
    global _driver
    if _driver is not None:
        _driver.quit()
        _driver = None
