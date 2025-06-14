import os
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import chromedriver_autoinstaller
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests

def send_slack_message(card1_money_amount, card2_money_amount):
    load_dotenv()
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

    if not SLACK_WEBHOOK_URL:
        print("エラー: SLACK_WEBHOOK_URL が設定されていません。")
        return

    message_text = "カード1: " + str(card1_money_amount) + "円\nカード2: " + str(card2_money_amount) + "円\n合計: " + str(card1_money_amount + card2_money_amount) + "円"


    payload = {
        "text": message_text
    }
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Slackにメッセージを送信しました。")
    except requests.exceptions.RequestException as e:
        print(f"Slackメッセージの送信に失敗しました: {e}")


def get_money_amount(driver):
    #カード明細ページへ
    driver.get(card_detail_url)

    #金額表示の親要素を特定
    parent_div = driver.find_element(By.CLASS_NAME, "stmt-about-payment__money__main__num")
    div_html_content = parent_div.get_attribute('outerHTML')
    soup = BeautifulSoup(div_html_content, 'html.parser')
    money_span = soup.find('span', class_='stmt-u-font-roboto')

    if money_span:
        # spanタグ内のテキストコンテンツを取得
        amount_text = money_span.get_text(strip=True) # strip=True で前後の空白を除去
        print(f"抽出された金額テキスト: {amount_text}")

        try:

            # シンプルにカンマを置換する場合
            numeric_amount = int(amount_text.replace(',', ''))
            print(f"数値として変換された金額: {numeric_amount}")
            return numeric_amount, driver
        except ValueError:
            print(f"エラー: 金額を数値に変換できませんでした: '{amount_text}'")
            return None
    else:
        print("エラー: 指定されたspanタグが見つかりませんでした。")
        return None

def get_website_content(url):
    load_dotenv()
    id = os.getenv("ID")
    pw = os.getenv("PW")
    driver = None # 初期化
    chrome_driver_path = chromedriver_autoinstaller.install()
    service = Service(executable_path=chrome_driver_path)
    options = webdriver.ChromeOptions()
    
    try:
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(5) 
        driver.get(target_url) # 対象のURLをここに記述してください

        # 明示的な待機: ID 'user_id' を持つ要素がDOMに存在し、可視になるまで最大10秒待機
        idForm = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "user_id"))
        )

        # inputにテキストを送信
        idForm.send_keys(id)

        #次へボタン 親要素を特定
        parent_div = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "cta001")) # クリック可能になるまで待つ
        )
        #次へボタン を特定しクリック
        next_button = parent_div.find_element(By.XPATH, ".//div[text()='次へ']").click()

        
        pwForm = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "password_current"))
        )
        
        #inputにテキストを送信
        pwForm.send_keys(pw)

        #次へボタン親要素を特定
        parent_div = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "cta011")) # クリック可能になるまで待つ
        )
        #次へボタン を特定しクリック
        next_button = parent_div.find_element(By.XPATH, ".//div[text()='次へ']").click()
        time.sleep(5)
        
        card1_money_amount, driver = get_money_amount(driver)
        #カード切り替え
        select_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "j_idt631:card"))
        )
        selector = Select(select_element)
        selector.select_by_value("1")

        #time.sleep(10)
        card2_money_amount, driver = get_money_amount(driver)

        return card1_money_amount, card2_money_amount

    except TimeoutException:
        print("エラー: 指定された時間内に要素 'user_id' が見つかりませんでした。")
        print("HTMLのIDが正しいか、ページのロードに時間がかかっていないか確認してください。")
    except NoSuchElementException:
        print("エラー: ID 'user_id' を持つ要素が見つかりませんでした。")
        print("IDが正確か、Javascriptで動的に変更されていないか確認してください。")
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
    finally:
        if driver:
            driver.quit()
            print("WebDriverを閉じました。")

if __name__ == "__main__":
    target_url = "https://www.rakuten-card.co.jp/e-navi/members/?l-id=corp_oo_top_to_loginenavi" # アクセスしたいURLを指定してください#
    card_detail_url = "https://www.rakuten-card.co.jp/e-navi/members/statement/index.xhtml?tabNo=0"

    card1_money_amount, card2_money_amount = get_website_content(target_url)
    send_slack_message(card1_money_amount, card2_money_amount)

    