import os
import time
import requests
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from bs4 import BeautifulSoup

# --- 環境変数のロード (ローカルテスト用、Lambdaでは環境変数から直接取得) ---
load_dotenv()

# Lambdaの環境変数、またはローカルの.envから取得
TARGET_URL = os.getenv("TARGET_URL", "https://www.rakuten-card.co.jp/e-navi/members/?l-id=corp_oo_top_to_loginenavi")
CARD_DETAIL_URL = os.getenv("CARD_DETAIL_URL", "https://www.rakuten-card.co.jp/e-navi/members/statement/index.xhtml?tabNo=0")
LOGIN_USER_ID = os.getenv("ID") # .envのID
LOGIN_PASSWORD = os.getenv("PW") # .envのPW

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# --- Slackメッセージ送信関数 ---
def send_slack_message(card1_money_amount, card2_money_amount):
    if not SLACK_WEBHOOK_URL:
        print("エラー: SLACK_WEBHOOK_URL が設定されていません。Slack通知をスキップします。")
        return

    message_text = (
        f"カード1: {card1_money_amount}円\n"
        f"カード2: {card2_money_amount}円\n"
        f"合計: {card1_money_amount + card2_money_amount}円"
    )

    payload = {
        "text": message_text
    }
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Slackにメッセージを送信しました。")
    except requests.exceptions.RequestException as e:
        print(f"Slackメッセージの送信に失敗しました: {e}")
        if 'response' in locals():
            print(f"Slackレスポンス: {response.text}")

# --- 金額取得関数 ---
def get_money_amount(driver, card_detail_url): # URLを引数に追加
    #カード明細ページへ
    print(f"カード明細ページへ移動: {card_detail_url}")
    driver.get(card_detail_url)

    # 金額表示の親要素を特定するまで待機
    print("金額表示のdiv要素を待機中...")
    parent_div = WebDriverWait(driver, 30).until( # タイムアウトを長めに
        EC.presence_of_element_located((By.CLASS_NAME, "stmt-about-payment__money__main__num"))
    )
    print("金額表示のdiv要素が見つかりました。")

    div_html_content = parent_div.get_attribute('outerHTML')
    soup = BeautifulSoup(div_html_content, 'html.parser')
    money_span = soup.find('span', class_='stmt-u-font-roboto')

    if money_span:
        amount_text = money_span.get_text(strip=True)
        print(f"抽出された金額テキスト: {amount_text}")

        try:
            numeric_amount = int(amount_text.replace(',', ''))
            print(f"数値として変換された金額: {numeric_amount}")
            return numeric_amount
        except ValueError:
            print(f"エラー: 金額を数値に変換できませんでした: '{amount_text}'")
            return None
    else:
        print("エラー: 指定されたspanタグが見つかりませんでした。")
        return None

# --- メインのWebサイト操作関数 (Lambdaのハンドラとして動作) ---
def handler(event, context):
    driver = None # 初期化
    card1_money_amount = None
    card2_money_amount = None

    try:
        # Dockerfileで設定したChromedriverとChromeバイナリのパス
        # 環境変数から取得
        chrome_driver_path = os.environ.get("CHROME_DRIVER_PATH", "/opt/chromedriver")
        chrome_binary_path = os.environ.get("CHROME_BINARY_PATH", "/opt/chrome/chrome")

        service = Service(executable_path=chrome_driver_path)
        options = webdriver.ChromeOptions()

        # Lambdaで必須のオプション
        options.add_argument('--headless') # ヘッドレスモードで実行
        options.add_argument('--no-sandbox') # サンドボックス無効化 (Lambdaで必須)
        options.add_argument('--disable-dev-shm-usage') # 共有メモリの使用を無効化 (Lambdaで必須)
        options.add_argument('--disable-gpu') # GPU使用を無効化
        options.add_argument('--window-size=1920x1080') # ウィンドウサイズ指定 (必要に応じて調整)
        options.add_argument('--single-process') # シングルプロセスモード (Lambdaでリソース節約)
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-translate')
        options.add_argument('--hide-scrollbars')
        options.add_argument('--metrics-recording-only')
        options.add_argument('--mute-audio')
        options.add_argument('--no-first-run')
        options.add_argument('--disable-setuid-sandbox') # 追加
        options.add_argument('--disable-backgrounding-occluded-windows') # 追加
        options.add_argument('--disable-ipc-flooding-protection') # 追加
        options.add_argument('--disable-renderer-backgrounding') # 追加
        # options.add_argument('--remote-debugging-port=9222') # デバッグ用 (本番では不要)
        options.binary_location = chrome_binary_path # Chromeバイナリのパスを指定

        # WebDriverの起動
        print("WebDriverを起動しています...")
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(10) # 暗黙的待機 (明示的待機を優先)

        # ログインページへアクセス
        print(f"ログインページへアクセス: {TARGET_URL}")
        driver.get(TARGET_URL)

        # ID 'user_id' のinput要素にユーザーIDを入力
        print("ユーザーID入力欄を待機中...")
        idForm = WebDriverWait(driver, 30).until( # タイムアウトを長めに
            EC.element_to_be_clickable((By.ID, "user_id"))
        )
        print(f"ユーザーID入力欄が見つかりました。'{LOGIN_USER_ID}'を入力します。")
        idForm.send_keys(LOGIN_USER_ID)

        # ログインフォームの「次へ」ボタンをクリック (cta001)
        print("ログインフォームの次へボタン (cta001) を待機中...")
        parent_div_cta001 = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.ID, "cta001"))
        )
        print("次へボタン (cta001) が見つかりました。クリックします。")
        parent_div_cta001.find_element(By.XPATH, ".//div[text()='次へ']").click()

        # パスワード入力欄 (ID: 'password_current')
        print("パスワード入力欄 (password_current) を待機中...")
        pwForm = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "password_current"))
        )
        print(f"パスワード入力欄が見つかりました。パスワードを入力します。")
        pwForm.send_keys(LOGIN_PASSWORD)

        # パスワード入力後の「次へ」ボタンをクリック (cta011)
        print("パスワード入力後の次へボタン (cta011) を待機中...")
        parent_div_cta011 = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.ID, "cta011"))
        )
        print("次へボタン (cta011) が見つかりました。クリックします。")
        parent_div_cta011.find_element(By.XPATH, ".//div[text()='次へ']").click()

        # ログイン後のページ読み込みを待つ（金額表示のdivなど）
        print("ログイン後のページ読み込みを待機中...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "stmt-about-payment__money__main__num"))
        )
        print("ログイン後のページがロードされました。")

        # --- カード1の金額取得 ---
        print("カード1の金額を取得します...")
        card1_money_amount = get_money_amount(driver, CARD_DETAIL_URL)

        # --- カード切り替え ---
        # j_idt631:card の <select> 要素を待機
        print("カード切り替えドロップダウン (j_idt631:card) を待機中...")
        select_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "j_idt631:card"))
        )
        print("カード切り替えドロップダウンが見つかりました。")

        selector = Select(select_element)
        print("value '1' のオプションを選択します。")
        selector.select_by_value("1") # 2枚目のカードを選択

        # カード切り替え後のページ読み込みを待つ（金額表示のdivなど）
        print("カード切り替え後のページ読み込みを待機中...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "stmt-about-payment__money__main__num"))
        )
        print("カード切り替え後のページがロードされました。")

        # --- カード2の金額取得 ---
        print("カード2の金額を取得します...")
        card2_money_amount = get_money_amount(driver, CARD_DETAIL_URL)

        # Slack通知
        if card1_money_amount is not None and card2_money_amount is not None:
            send_slack_message(card1_money_amount, card2_money_amount)
        else:
            send_slack_message("取得失敗", "取得失敗") # 金額取得が一部でも失敗した場合の通知

        print("すべての処理が完了しました。")
        return {
            'statusCode': 200,
            'body': f'Scraping completed. Card1: {card1_money_amount}, Card2: {card2_money_amount}'
        }

    except TimeoutException as e:
        error_message = f"エラー: 要素の待機中にタイムアウトしました。{e}"
        print(error_message)
        send_slack_message("エラー", f"スクレイピング失敗: タイムアウト\n{error_message}")
        return {
            'statusCode': 500,
            'body': f'Scraping failed: Timeout - {error_message}'
        }
    except NoSuchElementException as e:
        error_message = f"エラー: 必要な要素が見つかりませんでした。{e}"
        print(error_message)
        send_slack_message("エラー", f"スクレイピング失敗: 要素見つからず\n{error_message}")
        return {
            'statusCode': 500,
            'body': f'Scraping failed: No such element - {error_message}'
        }
    except Exception as e:
        error_message = f"予期せぬエラーが発生しました: {e}"
        print(error_message)
        send_slack_message("エラー", f"スクレイピング中に予期せぬエラー\n{error_message}")
        return {
            'statusCode': 500,
            'body': f'Scraping failed: Unexpected error - {error_message}'
        }
    finally:
        if driver:
            driver.quit()
            print("WebDriverを閉じました。")