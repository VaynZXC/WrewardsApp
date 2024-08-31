from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import QDialog, QCheckBox, QMessageBox, QApplication, QMainWindow, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFrame, QListWidget
from PySide6.QtWidgets import QListWidgetItem, QWidget, QHBoxLayout, QGraphicsDropShadowEffect, QTextEdit, QComboBox, QSizePolicy, QStackedWidget
from PySide6.QtCore import Qt, QPoint, Signal, QThread, Slot, QTimer, QSize, QObject
from PySide6.QtGui import QMouseEvent, QFont, QColor, QPainter, QTextOption, QMovie
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import undetected_chromedriver as uc
from selenium import webdriver
import sys
import json
import time
import datetime
import random
import requests
from queue import Queue
from pygame import mixer as mixer
import os
import zipfile
from threading import Lock
import tempfile
import psutil
from datetime import datetime
import re
from pywinauto import Desktop
from twocaptcha import TwoCaptcha

from main_window import Ui_MainWindow

current_user_id = None

def get_user_id():
    return current_user_id

solver = TwoCaptcha('4b457d61d55238c310be16925bbff7f5')

CHROMEDRIVER_PATH = 'chromdriver/chromedriver.exe'

# Костыли
class ClickableLabel(QLabel):
    clicked = QtCore.Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
        
class ClickableFrame(QFrame):
    clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.label = ClickableLabel(self)
        self.label.clicked.connect(self.clicked.emit)
        
class AccountSettingsDialog(QDialog):
    def __init__(self, account_id, account_name, cookies, twitch_cookies, messages, account_proxy, parent=None):
        super(AccountSettingsDialog, self).__init__(parent)
        self.account_id = account_id
        self.account_name = account_name
        self.cookies = cookies
        self.twitch_cookies = twitch_cookies
        self.messages = messages
        self.account_proxy = account_proxy
        self.init_ui()
        self.setGeometry(100, 100, 800, 600)
        self.center_on_screen()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QDialog {
                background-color: #333;
                color: white;
            }
            QLabel {
                margin-left: 20px;
            }
            QTextEdit {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
                padding: 5px;
                margin-top: 5px;
                margin-bottom: 5px;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #666;
                padding: 5px;
                margin: 5px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)

        self.account_name_edit = QLineEdit(self)
        self.account_name_edit.setText(self.account_name)
        self.account_name_edit.setPlaceholderText("Enter account name (up to 30 chars)")
        self.account_name_edit.setMaxLength(30)
        font = QFont()
        font.setFamilies([u"Gotham Pro Black"])
        font.setPointSize(15)
        self.account_name_edit.setFont(font)
        layout.addWidget(self.account_name_edit)

        # Куки
        self.cookies_edit = QTextEdit()
        try:
            cookies_json = json.loads(self.cookies)
            self.cookies_edit.setPlainText(json.dumps(cookies_json, indent=4))
        except json.JSONDecodeError:
            self.cookies_edit.setPlainText("Неверно заданы cookies.")
        self.cookies_edit.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self.cookies_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        layout.addWidget(self.cookies_edit)

        # Сообщения
        self.messages_edit = QTextEdit()
        self.messages_edit.setPlainText("\n".join(self.messages.splitlines()))
        self.messages_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        layout.addWidget(self.messages_edit)

        self.account_proxy_edit = QLineEdit(self)
        self.account_proxy_edit.setText(self.account_proxy)
        self.account_proxy_edit.setPlaceholderText("Прокси")
        self.account_proxy_edit.setMaxLength(100)
        font = QFont()
        font.setFamilies([u"Gotham Pro Black"])
        font.setPointSize(12)
        self.account_proxy_edit.setFont(font)
        layout.addWidget(self.account_proxy_edit)
        
        # Twitch cookies
        self.twitch_cookies_edit = QTextEdit()
        try:
            twitch_cookies_json = json.loads(self.twitch_cookies)
            self.twitch_cookies_edit.setPlainText(json.dumps(twitch_cookies_json, indent=4))
        except json.JSONDecodeError:
            self.twitch_cookies_edit.setPlainText("Неверно заданы twitch cookies.")
        self.twitch_cookies_edit.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self.twitch_cookies_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        layout.addWidget(self.twitch_cookies_edit)

        # Кнопки
        buttons_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        font = QFont()
        font.setFamilies([u"Gotham Pro Black"])
        font.setPointSize(12)
        save_button.setFont(font)
        cancel_button.setFont(font)
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        
        save_button.clicked.connect(self.save_changes)
        cancel_button.clicked.connect(self.reject)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def save_changes(self):
        user_id = get_user_id()
        if user_id is None:
            QMessageBox.critical(self, "Error", "User ID is not set. Please login again.")
            return

        data = {
            'account_id': self.account_id,
            'name': self.account_name_edit.text(),
            'cookies': self.cookies_edit.toPlainText(),
            'twitch_cookies': self.twitch_cookies_edit.toPlainText(),
            'messages': self.messages_edit.toPlainText(),
            'account_proxy': self.account_proxy_edit.text()
        }
        response = requests.post('http://77.232.131.189:5000/update_kick_account', json=data)
        if response.status_code == 200:
            QMessageBox.information(self, "Success", "Account successfully updated.")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to update account. Server responded with an error.")
    
    def center_on_screen(self):
        screen_geometry = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())
        
class AddAccountDialog(QDialog):
    def __init__(self, parent=None):
        super(AddAccountDialog, self).__init__(parent)
        self.setWindowTitle("Add New Account")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(800, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QDialog {
                background-color: #333;
                color: white;
            }
            QLabel {
                margin-left: 20px;
            }
            QTextEdit {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
                padding: 5px;
                margin-top: 5px;
                margin-bottom: 5px;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #666;
                padding: 5px;
                margin: 5px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #777;
            }
            QCheckBox {
                margin-left: 10px;
            }
        """)

        # Название аккаунта
        self.account_name_edit = QLineEdit(self)
        self.account_name_edit.setPlaceholderText("Enter account name (up to 30 chars)")
        self.account_name_edit.setMaxLength(30)
        font = QFont()
        font.setFamilies([u"Gotham Pro Black"])
        font.setPointSize(15)
        self.account_name_edit.setFont(font)
        layout.addWidget(self.account_name_edit)

        # Куки
        self.cookies_edit = QTextEdit(self)
        self.cookies_edit.setPlaceholderText("Вставьте сюда куки...")
        layout.addWidget(self.cookies_edit)

        # Сообщения
        self.messages_edit = QTextEdit(self)
        self.messages_edit.setPlaceholderText("Вставьте сюда сообщения...")
        layout.addWidget(self.messages_edit)

        # Переключатель для Twitch cookies
        self.use_twitch_cookies_checkbox = QCheckBox("Использовать Twitch cookies", self)
        self.use_twitch_cookies_checkbox.stateChanged.connect(self.toggle_twitch_cookies)
        layout.addWidget(self.use_twitch_cookies_checkbox)

        # Twitch cookies
        self.twitch_cookies_edit = QTextEdit(self)
        self.twitch_cookies_edit.setPlaceholderText("Вставьте сюда twitch cookies...")
        self.twitch_cookies_edit.setFixedHeight(100)
        layout.addWidget(self.twitch_cookies_edit)

        # Кнопки
        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Сохранить", self)
        self.cancel_button = QPushButton("Отменить", self)
        font = QFont()
        font.setFamilies([u"Gotham Pro Black"])
        font.setPointSize(12)
        self.save_button.setFont(font)
        self.cancel_button.setFont(font)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)

        self.save_button.clicked.connect(self.save_account)
        self.cancel_button.clicked.connect(self.reject)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

        # Скрытие поля twitch_cookies_edit по умолчанию
        self.twitch_cookies_edit.hide()

    def toggle_twitch_cookies(self, state):
        #print(f"Twitch cookies checkbox state changed: {state}")  # Отладочная печать
        if state == 2:
            self.twitch_cookies_edit.show()
        else:
            self.twitch_cookies_edit.hide()
        self.adjustSize()  # Обновляем размер окна после изменения видимости элемента

    def save_account(self):
        user_id = get_user_id()
        if user_id is None:
            QMessageBox.critical(self, "Error", "User ID is not set. Please login again.")
            return

        twitch_cookies = self.twitch_cookies_edit.toPlainText() if self.use_twitch_cookies_checkbox.isChecked() else "default cookies"

        data = {
            'user_id': user_id,
            'name': self.account_name_edit.text(),
            'cookies': self.cookies_edit.toPlainText(),
            'twitch_cookies': twitch_cookies,
            'messages': self.messages_edit.toPlainText()
        }
        response = requests.post('http://77.232.131.189:5000/add_kick_account', json=data)
        if response.status_code == 200:
            QMessageBox.information(self, "Success", "Account successfully added.")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to add account. Server responded with an error.")
  
class ConfirmationRequest(QObject):
    confirmation_needed = Signal(str)

confirmation_request = ConfirmationRequest()
  
def bring_window_to_front(account_name):
    try:
        low_case_name = account_name.lower()
        windows = Desktop(backend="uia").windows(title_re=f".*{low_case_name}.*")
        if windows:
            window = windows[0]
            window.set_focus()
        else:
            print(f"Окно для аккаунта {account_name} не найдено")
    except Exception as e:
        print(f"Ошибка при попытке активировать окно: {e}")

def list_all_windows():
    windows = Desktop(backend="uia").windows()
    for window in windows:
        print(f'Title: {window.window_text()}')

def show_confirmation_dialog(message):
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setWindowTitle("Подтверждение")
    msg_box.setText(message)
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.No)
    msg_box.setWindowFlag(Qt.WindowStaysOnTopHint)
    #msg_box.setWindowModality(Qt.NonModal)
    return msg_box.exec() == QMessageBox.Yes
  
class AccountManager:
    def __init__(self, data_fetcher_thread):
        self.data_fetcher_thread = data_fetcher_thread
        self.active_drivers_count = 0
        self.account_widgets = []
        self.lock = Lock()
        self.wg_pochinka_enabled = True
        self.drivers = []
        self.current_sub_account = None
        confirmation_request.confirmation_needed.connect(self.on_confirmation_needed)

    def add_account_widget(self, account_widget):
        self.account_widgets.append(account_widget)

    def on_chat_writer_started(self):
        with self.lock:
            self.active_drivers_count += 1
            if self.active_drivers_count == 1:
                self.data_fetcher_thread.start_parser()
    
    def on_chat_writer_stopped(self):
        with self.lock:
            self.active_drivers_count -= 1
            if self.active_drivers_count == 0:
                self.data_fetcher_thread.stop_parser()

    def are_drivers_running(self):
        with self.lock:
            return any(widget.is_running() for widget in self.account_widgets)

    def log_active_drivers_count(self):
        with self.lock:
            running_count = sum(widget.is_running() for widget in self.account_widgets)
            print(f"Active drivers count: {running_count}")

    def process_message(self, message):
        if not self.wg_pochinka_enabled:
            print('WG и pochinka отключены, пропускаем сообщение...')
            return
        
        if 'Раздача поинтов началась.' in message:
            for widget in self.account_widgets:
                if widget.thread and widget.thread.isRunning():
                    widget.thread.set_wg_active(True)
            print(f"Запуск WG сообщения...")

        if 'Починка началась' in message:
            split_message = message.split(' ')
            key_word = split_message[2].lower()
            #print(f"Ключевое слово: {key_word}")
            confirmation_request.confirmation_needed.emit(key_word)
            
        if 'Победитель' in message:
            split_message = message.split(' ')
            winner = split_message[1].lower()
            print(f'Победитель {winner}')
            #list_all_windows()
            for widget in self.account_widgets:
                account_name = widget.thread.account_name.lower()
                if account_name == winner:
                    sound = os.path.join('sounds/12.mp3')
                    self.play_sound(sound)
                    bring_window_to_front(account_name)
                    print(f"ВЫ ВЫИГРАЛИ ПОЧИНКУ")
                    
    def on_confirmation_needed(self, key_word):
        if show_confirmation_dialog("Началась починка. Отправить !join сообщение всем драйверам?"):
            for widget in self.account_widgets:
                if widget.thread and widget.thread.isRunning():
                    widget.thread.send_message_signal.emit('!join')
            print("Сообщение отправлено всем драйверам.")
        else:
            print("Сообщение не отправлено.")
                    
    def set_wg_pochinka_enabled(self, enabled):
        self.wg_pochinka_enabled = enabled
        #print(f'WG и Pochinka сообщения включены: {self.wg_pochinka_enabled}')
    
    def set_current_sub_account(self, sub_account_id):
        self.current_sub_account = sub_account_id
                    
    def get_selected_accounts(self):
        selected_accounts = []
        for widget in self.account_widgets:
            if widget.checkbox.isChecked():
                selected_accounts.append(widget.account_id)
        print(f"Selected accounts retrieved: {selected_accounts}")
        return selected_accounts

    def play_sound(self, file_path):
        mixer.init()
        mixer.music.load(file_path)
        mixer.music.set_volume(0.15)
        mixer.music.play()


# Парсер магазина
PRODUCT_SELECTION_FILE = 'product_selection.json'

def load_product_selection():
    if os.path.exists(PRODUCT_SELECTION_FILE):
        with open(PRODUCT_SELECTION_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_product_selection(product_selection):
    with open(PRODUCT_SELECTION_FILE, 'w') as file:
        json.dump(product_selection, file, indent=4)
  
def load_account_points(filename='account_points.txt'):
    account_points = {}
    try:
        with open(filename, 'r') as file:
            for line in file:
                parts = line.strip().split(',')
                if len(parts) == 4:
                    _, account_name, thousands, hundreds = parts
                    total_points = int(thousands) * 1000 + int(hundreds)
                    account_points[account_name] = total_points
    except FileNotFoundError:
        print(f"Файл {filename} не найден.")
    return account_points
        
class ShopParserThread(QThread):
    def __init__(self, account_name, twitch_cookies, account_proxy, product, parent=None):
        super(ShopParserThread, self).__init__(parent)
        self.account_name = account_name
        self.twitch_cookies = twitch_cookies
        self.account_proxy = account_proxy
        self.product = product
        self.product_status = None
        self.is_bought = False
        self.is_running = True
        self.product_collected_file = "product_collected.txt"
        self.points_file = "account_points.txt"
        self.driver = None
        self.set_product_element()
        
    def mark_product_collected(self):
        try:
            with open(self.product_collected_file, 'r') as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    data = {}
        except FileNotFoundError:
            data = {}
            
        today = datetime.now().date().strftime('%Y-%m-%d')
        if data.get(self.account_name) != today:
            data[self.account_name] = today
            with open(self.product_collected_file, 'w') as file:
                json.dump(data, file)

    def set_product_element(self):
        if self.product == '$100 Steam Gift Card':
            self.product_element = '//*[@id="__next"]/div/div[3]/div[3]/div[2]/div/div/div[1]/div[17]/div[2]/div[2]/div'
        if self.product == '$100 Amazon Gift Card':
            self.product_element = '//*[@id="__next"]/div/div[3]/div[3]/div[2]/div/div/div[1]/div[16]/div[2]/div[2]/div'
        if self.product == '$125 SHARE in a WRewards':
            self.product_element = '//*[@id="__next"]/div/div[3]/div[3]/div[2]/div/div/div[1]/div[15]/div[2]/div[2]/div'
        if self.product == 'Pachinko Drop (ON STREAM)':
            self.product_element = '//*[@id="__next"]/div/div[3]/div[3]/div[2]/div/div/div[1]/div[14]/div[2]/div[2]/div'
        if self.product == '$200 in ETH':
            self.product_element = '//*[@id="__next"]/div/div[3]/div[3]/div[2]/div/div/div[1]/div[13]/div[2]/div[2]/div'
        if self.product == '$200 in Litecoin':
            self.product_element = '//*[@id="__next"]/div/div[3]/div[3]/div[2]/div/div/div[1]/div[12]/div[2]/div[2]/div'
        if self.product == 'Nintendo Switch':
            self.product_element = '//*[@id="__next"]/div/div[3]/div[3]/div[2]/div/div/div[1]/div[11]/div[2]/div[2]/div'
        if self.product == 'Oura Smart Ring Gen 3':
            self.product_element = '//*[@id="__next"]/div/div[3]/div[3]/div[2]/div/div/div[1]/div[10]/div[2]/div[2]/div'
        if self.product == 'PlayStation 5 (PS5)':
            self.product_element = '//*[@id="__next"]/div/div[3]/div[3]/div[2]/div/div/div[1]/div[9]/div[2]/div[2]/div'
            

    def run(self):
        if not self.product:
            print('Выберите продукт.')
            return
        
        try:
            self.driver = self.get_chromedriver(
                use_proxy = True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            if not self.driver:
                print(f'Не удалось инициализировать драйвер Chrome [{self.account_name}]')
                return

            print(f'Запущен парсер для магазина на аккаун {self.account_name}')

            site1 = f'https://www.twitch.tv/kishimy2'
            site2 = f'https://www.wrewards.com'
            
            # self.driver.get('https://pr-cy.ru/browser-details/')
            # time.sleep(10)
            
            self.driver.get(site1)
            self.add_cookies()
            
            self.driver.execute_script("window.open('');")
            second_tab = self.driver.window_handles[1]
            self.driver.switch_to.window(second_tab)
            self.driver.set_page_load_timeout(50)
            try:
                self.driver.get(site2)
            except TimeoutException:
                pass

            #time.sleep(100000)

            wait = WebDriverWait(self.driver, 10)

            #Логинимся в аккаунт
            for i in range(10):
                try:
                    print('Пытаемся нажать на кнопку login.')
                    button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[text()='Login']")))
                    button.click()
                    break
                except Exception:
                    print('Кнопки login не найдено.')
                    time.sleep(5)
                    
            try:
                button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Log in via Twitch')]")))
                button.click()
            except NoSuchElementException:
                print('Кнопки login2 не найдено.')
            
            self.driver.get('https://www.wrewards.com/points-shop')
            
            #time.sleep(3)
            
            try:
                product = wait.until(EC.element_to_be_clickable((By.XPATH, self.product_element)))
                if button:
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", product)
                    print(f'{self.account_name} Продукт найден.')
                    while not self.is_bought:
                        if product.text == 'SOLD OUT':
                            print(f'[{self.account_name}] {self.product} нет в наличии.')
                            time.sleep(1)
                        elif product.text == 'BUY':
                            try:
                                print(f'[{self.account_name}] Покупаем {self.product}')
                                product.click()
                                print(f'[{self.account_name}] 1')
                                accept_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="chakra-modal--body-:R1t1ium6:"]/div/div[2]/div[2]/div')))
                                print(f'[{self.account_name}] 2')
                                accept_btn.click()
                                print(f'[{self.account_name}] 3')
                                self.is_bought = True
                                print(f'[{self.account_name}] 4')
                            except Exception as e:
                                print(f'[{self.account_name}] Возникла проблема при покупке товара.')
                                print(e)
            except NoSuchElementException:
                print('Продукт не найден')
            time.sleep(2)
            
        except Exception as e:
            print(f'Ошибка в методе run() [{self.account_name}] ')
            print(e)
        finally:
            if self.is_running:
                self.quit()
                self.is_running = False

            
    def get_chromedriver(self, use_proxy=True, user_agent=None):
        try:
            chrome_options = uc.ChromeOptions()
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--incognito')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--profile-directory=Default')
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-dev-shm-usage')

            if user_agent:
                chrome_options.add_argument(f'--user-agent={user_agent}')

            if use_proxy and self.account_proxy:  
                split_proxy = self.account_proxy.split(':')
                PROXY_HOST = split_proxy[0]
                PROXY_PORT = split_proxy[1]
                PROXY_USER = split_proxy[2]
                PROXY_PASS = split_proxy[3]
                wire_options = {
                        'proxy': {
                            'https': f'https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
                        }
                    }
                
            user_data_dir = tempfile.mkdtemp()
            chrome_options.add_argument(f'--user-data-dir={user_data_dir}')

            if use_proxy and self.account_proxy:
                driver = uc.Chrome(options=chrome_options, seleniumwire_options=wire_options)
            else:
                driver = uc.Chrome(options=chrome_options)
                
            driver.set_window_size(1650, 900)
            return driver
        except Exception as e:
            print(f'Ошибка при инициализации Chromedriver: {e}')        
            return None 

    def add_cookies(self):
        try:
            cookies = json.loads(self.twitch_cookies)
            for cookie in cookies:
                if 'expirationDate' in cookie:
                    cookie['expiry'] = int(cookie['expirationDate'])
                    del cookie['expirationDate']
                if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                    cookie['sameSite'] = 'None'
                self.driver.add_cookie(cookie)
        except Exception as e:
            print(f'Ошибка при добавлении кук: {e}')      
            
    def stop(self):
        self.is_running = False
        print(f'Поток {self.account_name} остановлен')
        
class SelectProductDialog(QDialog):
    def __init__(self, parent=None):
        super(SelectProductDialog, self).__init__(parent)
        self.setWindowTitle("Выберите товар")
        self.setGeometry(100, 100, 300, 200)
        self.init_ui()
        self.center_on_screen()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QDialog {
                background-color: #333;
                color: white;
            }
            QListWidget {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
                padding: 5px;
                margin-top: 5px;
                margin-bottom: 5px;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #666;
                padding: 5px;
                margin: 5px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)

        self.product_list = QListWidget(self)
        products = ['$100 Steam Gift Card', '$100 Amazon Gift Card', '$125 SHARE in a WRewards', 'Pachinko Drop (ON STREAM)', '$200 in ETH', '$200 in Litecoin', 'Nintendo Switch', 'Oura Smart Ring Gen 3', 'PlayStation 5 (PS5)']
        self.product_list.addItems(products)
        layout.addWidget(self.product_list)

        self.select_button = QPushButton("Выбрать", self)
        self.select_button.clicked.connect(self.select_product)
        layout.addWidget(self.select_button)

    def select_product(self):
        selected_items = self.product_list.selectedItems()
        if selected_items:
            self.selected_product = selected_items[0].text()
            self.accept()

    def get_selected_product(self):
        return getattr(self, 'selected_product', None)
    
    def center_on_screen(self):
        screen_geometry = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())     
                
class ShopAccountWidget(QWidget):
    def __init__(self, account_id, account_name, twitch_cookies, account_proxy, points, parent=None):
        super().__init__(parent)
        self.account_id = account_id
        self.account_name = account_name
        self.twitch_cookies = twitch_cookies
        self.account_proxy = account_proxy
        self.points = points
        self.init_ui()
        self.load_selected_product()

    def init_ui(self):
        layout = QHBoxLayout(self)
        self.setMinimumHeight(50)
        self.setStyleSheet("QWidget { margin-left: 10px; border-radius: 3px; }")

        font_large = QFont()
        font_large.setFamilies([u"Gotham Pro Black"])
        font_large.setPointSize(14)

        self.account_label = QLabel(f"{self.account_name} ({self.points} поинтов)")
        self.account_label.setFont(font_large)
        layout.addWidget(self.account_label, 4)

        self.select_product_button = QPushButton("Выбрать товар")
        self.select_product_button.setStyleSheet("QPushButton { padding: 5px; border-radius: 3px; }")
        layout.addWidget(self.select_product_button, 1)
        self.select_product_button.clicked.connect(self.select_product)

        self.start_button = QPushButton("Запустить")
        self.start_button.setStyleSheet("QPushButton { padding: 5px; border-radius: 3px; }")
        layout.addWidget(self.start_button, 1)
        self.start_button.clicked.connect(self.start_parser)

        self.setLayout(layout)

    def select_product(self):
        dialog = SelectProductDialog(self)
        if dialog.exec() == QDialog.Accepted:
            selected_product = dialog.get_selected_product()
            if selected_product:
                self.select_product_button.setText(selected_product)
                self.save_selected_product(selected_product)

    def start_parser(self):
        if self.select_product_button.text() != 'Выбрать товар':
            self.thread = ShopParserThread(self.account_name, self.twitch_cookies, self.account_proxy, self.select_product_button.text())
            self.thread.start()
        else:
            print('Выберите товар.')
        
    def save_selected_product(self, product):
        product_selection = load_product_selection()
        product_selection[self.account_id] = product
        save_product_selection(product_selection)

    def load_selected_product(self):
        product_selection = load_product_selection()
        selected_product = product_selection.get(str(self.account_id))  # Приведение к строке
        if selected_product:
            self.select_product_button.setText(selected_product)
      
class ShopParserWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Парсер магазина")
        self.setGeometry(100, 100, 750, 600)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.init_ui()
        self.account_points = load_account_points()
        self.load_accounts()
        self.old_pos = None
        self.center_on_screen()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        self.setStyleSheet("""
        QWidget {
            background-color: #333;
            color: white;
            margin: 2px;
            border-radius: 3px;
        }
        QPushButton {
            background-color: #555;
            color: white;
            border: 1px solid #666;
            padding: 5px;
            margin: 5px;
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: #777;
        }
        QListWidget {
            background-color: #2b2b2b;
            border: none;
            border-radius: 5px;
        }
        """)

        self.header = QWidget(self)
        self.header.setFixedHeight(40)
        self.header.setStyleSheet("background-color: #444; border-radius: 5px;")
        layout.addWidget(self.header)

        self.close_button = QPushButton("X", self.header)
        self.close_button.setStyleSheet("QPushButton { color: red; font-weight: bold; border-radius: 5px; }")
        self.close_button.clicked.connect(self.close)
        self.close_button.setGeometry(685, 5, 40, 30)

        self.account_list = QListWidget()
        layout.addWidget(self.account_list)
        
        self.minimize_button = QPushButton("-", self.header)
        self.minimize_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        self.minimize_button.clicked.connect(self.showMinimized)
        self.minimize_button.setGeometry(650, 5, 40, 30)
        

    def load_accounts(self):
        user_id = get_user_id()
        if user_id is None:
            print("User ID is not set. Cannot load accounts.")
            return

        self.account_list.clear()

        try:
            response = requests.get('http://77.232.131.189:5000/get_kick_accounts', params={'user_id': user_id})
            if response.status_code == 200:
                accounts_data = response.json()
                accounts = accounts_data.get('accounts', [])
                sorted_accounts = sorted(accounts, key=lambda x: x['id'])
                for account in sorted_accounts:
                    self.add_account_to_list(account['id'], account['name'], account['twitch_cookies'], account['account_proxy'])
            else:
                print(f"Failed to load accounts. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")

    def add_account_to_list(self, account_id, name, twitch_cookies, account_proxy):
        points = self.account_points.get(name, '0')
        account_widget = ShopAccountWidget(account_id, name, twitch_cookies, account_proxy, points, self)
        list_widget_item = QListWidgetItem(self.account_list)
        list_widget_item.setSizeHint(account_widget.sizeHint())
        self.account_list.addItem(list_widget_item)
        self.account_list.setItemWidget(list_widget_item, account_widget)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.header.rect().contains(event.position().toPoint()):
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def center_on_screen(self):
        screen_geometry = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())      
        
     
# Парсер календаря
class CalendarParserThread(QThread):
    finished = Signal(str)

    def __init__(self, account_name, proxy, twitch_cookies, stop_event, parent=None):
        super(CalendarParserThread, self).__init__(parent)
        self.account_name = account_name
        self.account_proxy = proxy
        self.twitch_cookies = twitch_cookies
        self.is_running = True
        self.stop_event = stop_event
        self.rewards_file = "collected_rewards.txt"
        self.points_file = "account_points.txt"
        self.driver = None
        
    def has_collected_reward(self):
        try:
            with open(self.rewards_file, 'r') as file:
                data = json.load(file)
        except (json.JSONDecodeError, FileNotFoundError):
            data = {}
        today = datetime.now().strftime('%Y-%m-%d')
        return data.get(self.account_name) == today

    def mark_reward_collected(self):
        try:
            with open(self.rewards_file, 'r') as file:
                data = json.load(file)
        except (json.JSONDecodeError, FileNotFoundError):
            data = {}

        today = datetime.now().strftime('%Y-%m-%d')
        if data.get(self.account_name) != today:
            data[self.account_name] = today
            with open(self.rewards_file, 'w') as file:
                json.dump(data, file)

    def save_points(self, account_name, points_count):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        updated = False
        lines = []
        try:
            with open(self.points_file, 'r') as file:
                lines = file.readlines()
            
            for i in range(len(lines)):
                if lines[i].split(',')[1] == account_name:
                    lines[i] = f'{current_time},{account_name},{points_count}\n'
                    updated = True
                    break
            
            if not updated:
                lines.append(f'{current_time},{account_name},{points_count}\n')
            
            with open(self.points_file, 'w') as file:
                file.writelines(lines)

        except FileNotFoundError:
            with open(self.points_file, 'w') as file:
                file.write(f'{current_time},{account_name},{points_count}\n')
            print(f'File {self.points_file} created and points for {account_name} saved successfully.')
        except Exception as e:
            print(f'Ошибка при сохранении поинтов для {account_name}: {e}')

    def run(self):
        if self.has_collected_reward():
            print(f'Аккаунт {self.account_name} уже забрал календарь сегодня.')
            self.finished.emit(self.account_name)
            return
        
        try: 
            self.driver = self.get_chromedriver(
                use_proxy = True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )   
            if not self.driver:
                print(f'Не удалось инициализировать драйвер Chrome [{self.account_name}]')
                self.finished.emit(self.account_name)
                return

            site1 = f'https://www.twitch.tv/kishimy2'
            site2 = f'https://www.wrewards.com'
            
            self.driver.get(site1)
            self.add_cookies()
            
            self.driver.execute_script("window.open('');")
            second_tab = self.driver.window_handles[1]
            self.driver.switch_to.window(second_tab)
            self.driver.set_page_load_timeout(50)
            try:
                self.driver.get(site2)
            except TimeoutException:
                pass

            #time.sleep(100000)

            wait = WebDriverWait(self.driver, 10)

            #Логинимся в аккаунт
            for i in range(10):
                try:
                    print('Пытаемся нажать на кнопку login.')
                    button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[text()='Login']")))
                    button.click()
                    break
                except Exception:
                    print('Кнопки login не найдено.')
                    time.sleep(5)
                    
            try:
                button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Log in via Twitch')]")))
                button.click()
            except NoSuchElementException:
                print('Кнопки login2 не найдено.')
            
            self.driver.get('https://www.wrewards.com/advent-calendar')
            
            try:
                banner = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'cookie-banner-button')))
                self.driver.execute_script("arguments[0].click();", banner)
            except NoSuchElementException:
                pass
                
            try:
                balance = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Balance']")))
                self.driver.execute_script("arguments[0].scrollIntoView(true);", balance)
                balance.click()
                
                child_element = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'W-Points')]")))
                parent_element = child_element.find_element(By.XPATH, "./..")
                if parent_element:
                    points_text = parent_element.text
                    self.points = re.search(r'\d[\d,]*', points_text).group()
                    self.save_points(self.account_name, self.points)
                    
            except NoSuchElementException:
                print(f'Элемент для просмотра поинтов не найден {self.account_name}.')
            except Exception as e:
                print(e)
                print(f'Не получилось посмотреть поинты на аккаунте {self.account_name}.')
                
            try:  
                time.sleep(3)
                flip_card = self.driver.find_element(By.CLASS_NAME, 'react-flip-card')
                self.driver.execute_script("arguments[0].scrollIntoView(true);", flip_card)
                time.sleep(3)
                flip_card.click()
                
                #Проходим капчу
                time.sleep(10)
                print('Проходим капчу.')
                try:
                    # Переключаемся на iframe с капчей
                    captcha_iframe = self.driver.find_element(By.CSS_SELECTOR, "iframe[title='reCAPTCHA']")
                    self.driver.switch_to.frame(captcha_iframe)
                    print('Переключились на iframe с капчей.')
                    
                    # Теперь ищем и нажимаем на капчу
                    captcha_checkbox = self.driver.find_element(By.CSS_SELECTOR, "div.recaptcha-checkbox-border")
                    captcha_checkbox.click()
                    print('Кликнули на чекбокс капчи.')
                    
                    # Возвращаемся обратно в основной контекст
                    self.driver.switch_to.default_content()
                except NoSuchElementException as e:
                    print(f'Элемент не найден: {e}')
                except Exception as e:
                    print(f'Произошла ошибка при работе с капчей: {e}')
                
                time.sleep(5)
                for i in range(10):
                    try:
                        print(f'Попытка {i}')
                        self.solve_captcha()
                        break
                    except NoSuchElementException:
                        print('Не удалось найти кнопку для капчи.')
                        time.sleep(5)
                    except Exception as e:
                        print(f'Не удалось обойти капчу. {e}') 
                        time.sleep(5)
                
                time.sleep(100000)
                after_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[text()='Claim raffle entry']")))
                if after_menu:
                    print(f'Акканут {self.account_name} забрал календарь. {self.points}')
                    self.mark_reward_collected()
                time.sleep(3)
            except NoSuchElementException:
                print(f'Акканут {self.account_name} уже забирал календарь сегодня. {self.points} поинтов.')
                self.mark_reward_collected()

        except Exception as e:
            print(f'Ошибка в методе run() [{self.account_name}] ')
            print(e)
        finally:
            self.stop()
            self.finished.emit(self.account_name)
            
    def get_chromedriver(self, use_proxy=True, user_agent=None):
        try:
            chrome_options = uc.ChromeOptions()
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--incognito')
            chrome_options.add_argument('--disable-infobars')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--profile-directory=Default')
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-dev-shm-usage')

            if user_agent:
                chrome_options.add_argument(f'--user-agent={user_agent}')

            if use_proxy and self.account_proxy:  
                split_proxy = self.account_proxy.split(':')
                PROXY_HOST = split_proxy[0]
                PROXY_PORT = split_proxy[1]
                PROXY_USER = split_proxy[2]
                PROXY_PASS = split_proxy[3]
                wire_options = {
                        'proxy': {
                            'https': f'https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
                        }
                    }
                
            user_data_dir = tempfile.mkdtemp()
            chrome_options.add_argument(f'--user-data-dir={user_data_dir}')

            driver = uc.Chrome(options=chrome_options, seleniumwire_options=wire_options)
            driver.set_window_size(1650, 900)
            return driver
        except Exception as e:
            print(f'Ошибка при инициализации Chromedriver: {e}')        
            return None 
    
    def solve_captcha(self):
        try:
            # Ждём некоторое время, чтобы капча загрузилась
            time.sleep(2)

            # Получаем sitekey капчи
            sitekey_element = self.driver.find_element(By.CSS_SELECTOR, "iframe")
            print('Нашли sitekey_element')
            sitekey = sitekey_element.get_attribute("src").split("k=")[1].split("&")[0]
            print('Нашли sitekey')
            page_url = self.driver.current_url

            # Решаем капчу через 2Captcha
            result = solver.recaptcha(
                sitekey=sitekey,
                url=page_url,
                method='userrecaptcha'
            )
            print('Капча решена, получен ответ от 2Captcha.')
            
            # Вводим решение капчи в соответствующее поле
            recaptcha_response = self.driver.find_element(By.CSS_SELECTOR, "#g-recaptcha-response")
            self.driver.execute_script("arguments[0].style.display = 'block';", recaptcha_response)  # Делаем поле видимым
            recaptcha_response.send_keys(result['code'])
            print('Ввод ответа в recaptcha_response')
            
            # Используем более общий селектор для поиска кнопки
            print('Пытаемся найти кнопку submit')
            submit_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Submit') or contains(text(), 'Verify') or @id='recaptcha-verify-button']")
            self.driver.execute_script("arguments[0].click();", submit_button)
            print('Кнопка submit нажата')

            print('Капча успешно решена и отправлена.')
            
            self.driver.switch_to.default_content()
        except Exception as e:
            print(f'Произошла ошибка при решении капчи: {e}')

    def add_cookies(self):
        try:
            cookies = json.loads(self.twitch_cookies)
            for cookie in cookies:
                if 'expirationDate' in cookie:
                    cookie['expiry'] = int(cookie['expirationDate'])
                    del cookie['expirationDate']
                if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                    cookie['sameSite'] = 'None'
                self.driver.add_cookie(cookie)
        except Exception as e:
            print(f'Ошибка при добавлении кук: {e}')
            
    def stop(self):
        self.is_running = False
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f'Ошибка при закрытии драйвера: {e}')
        #print(f'Поток {self.account_name} остановлен')
     
class CalendarAccountWidget(QWidget):
    finished = Signal()
    
    def __init__(self, account_id, account_name, proxy, twitch_cookies, parent=None):
        super().__init__(parent)
        self.account_id = account_id
        self.account_name = account_name
        self.proxy = proxy
        self.twitch_cookies = twitch_cookies
        self.reward_collected = False
        self.init_ui()
        self.thread = None

    def init_ui(self):
        layout = QHBoxLayout(self)
        self.setMinimumHeight(50)
        self.setStyleSheet("QWidget { margin-left: 10px; border-radius: 3px; }")

        font_large = QFont()
        font_large.setFamilies([u"Gotham Pro Black"])
        font_large.setPointSize(14)

        self.account_label = QLabel(self.account_name)
        self.account_label.setFont(font_large)
        layout.addWidget(self.account_label, 4)

        self.start_button = QPushButton("Запустить")
        self.start_button.setStyleSheet("QPushButton { padding: 5px; border-radius: 3px; }")
        layout.addWidget(self.start_button, 1)
        self.start_button.clicked.connect(self.start_calendar_parser)

        self.setLayout(layout)

    
    @Slot()
    def start_calendar_parser(self):
        if self.thread is None:
            self.thread = CalendarParserThread(self.account_name, self.proxy, self.twitch_cookies, self)
            self.thread.finished.connect(self.on_finished)
            self.thread.start()
        else:
            print(f'Поток для {self.account_name} уже запущен')

    @Slot(str)
    def on_finished(self, account_name):
        self.reward_collected = True 
        time.sleep(5)
        self.finished.emit() 
        if self.thread.driver:
            self.thread.quit()
            self.thread.wait() 
            self.thread = None
     
class CalendarParserWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Парсер календаря")
        self.setGeometry(100, 100, 550, 600)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.init_ui()
        self.load_accounts()
        self.old_pos = None
        self.center_on_screen()
        self.task_queue = Queue()
        self.is_running = False

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        self.setStyleSheet("""
        QWidget {
            background-color: #333;
            color: white;
            margin: 2px;
            border-radius: 3px;
        }
        QPushButton {
            background-color: #555;
            color: white;
            border: 1px solid #666;
            padding: 5px;
            margin: 5px;
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: #777;
        }
        QListWidget {
            background-color: #2b2b2b;
            border: none;
            border-radius: 5px;
        }
        """)

        self.header = QWidget(self)
        self.header.setFixedHeight(40)
        self.header.setStyleSheet("background-color: #444; border-radius: 5px;")
        layout.addWidget(self.header)

        self.close_button = QPushButton("X", self.header)
        self.close_button.setStyleSheet("QPushButton { color: red; font-weight: bold; border-radius: 5px; }")
        self.close_button.clicked.connect(self.close)
        self.close_button.setGeometry(485, 5, 40, 30)
        
        self.minimize_button = QPushButton("-", self.header)
        self.minimize_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        self.minimize_button.clicked.connect(self.showMinimized)
        self.minimize_button.setGeometry(450, 5, 40, 30)

        self.account_list = QListWidget()
        layout.addWidget(self.account_list)
        
        font = QFont()
        font.setPointSize(12)
        
        self.start_all_calendar_parsers_button = QPushButton("Запустить все")
        self.start_all_calendar_parsers_button.setFont(font)
        self.start_all_calendar_parsers_button.setCheckable(True)
        self.start_all_calendar_parsers_button.setChecked(False)
        self.start_all_calendar_parsers_button.clicked.connect(self.start_all_calendar_parsers)
        layout.addWidget(self.start_all_calendar_parsers_button)
        
    def start_all_calendar_parsers(self):
        self.start_all_calendar_parsers_button.setText('Идёт сбор календаря...')
        for index in range(self.account_list.count()):
            item = self.account_list.item(index)
            widget = self.account_list.itemWidget(item)
            if not widget.reward_collected:
                self.task_queue.put(widget)

        self.run_next_task()

    def run_next_task(self):
        if not self.task_queue.empty():
            widget = self.task_queue.get()
            self.is_running = True
            if not hasattr(widget, 'thread') or widget.thread is None:
                widget.thread = CalendarParserThread(widget.account_name, widget.proxy, widget.twitch_cookies, self)
                widget.thread.finished.connect(self.on_task_finished)
                widget.thread.start()
                #print(f'Запущен парсер для аккаунта: {widget.account_name}')
        else:
            self.is_running = False
            self.start_all_calendar_parsers_button.setText('Сбор завершен')

    @Slot()
    def on_task_finished(self):
        #print('on_task_finished called')
        self.kill_all_chrome_processes()
        self.run_next_task()

    def load_accounts(self):
        user_id = get_user_id()
        if user_id is None:
            print("User ID is not set. Cannot load accounts.")
            return

        self.account_list.clear()  # Очищаем список перед загрузкой новых аккаунтов

        try:
            response = requests.get('http://77.232.131.189:5000/get_kick_accounts', params={'user_id': user_id})
            if response.status_code == 200:
                accounts_data = response.json()
                accounts = accounts_data.get('accounts', [])
                sorted_accounts = sorted(accounts, key=lambda x: x['id'])
                for account in sorted_accounts:
                    self.add_account_to_list(account['id'], account['name'], account['account_proxy'], account.get('twitch_cookies', ''))
            else:
                print(f"Failed to load accounts. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")

    def add_account_to_list(self, account_id, name, proxy, twitch_cookies):
        account_widget = CalendarAccountWidget(account_id, name, proxy, twitch_cookies, self)
        list_widget_item = QListWidgetItem(self.account_list)
        list_widget_item.setSizeHint(account_widget.sizeHint())
        self.account_list.addItem(list_widget_item)
        self.account_list.setItemWidget(list_widget_item, account_widget)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.header.rect().contains(event.position().toPoint()):
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def center_on_screen(self):
        screen_geometry = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())
        
    def kill_all_chrome_processes(self):
        for process in psutil.process_iter(['pid', 'name']):
            if 'chrome' in process.info['name'].lower():
                try:
                    p = psutil.Process(process.info['pid'])
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
        
# Менеджек аккаунтов     
class AccountWidget(QWidget):
    def __init__(self, account_id, account_name, cookies, twitch_cookies, messages, account_proxy,  manager_window, parent=None):
        super().__init__(parent)
        self.account_id = str(account_id) 
        self.account_name = account_name
        self.cookies = cookies
        self.twitch_cookies = twitch_cookies
        self.messages = messages
        self.account_proxy = account_proxy
        self.manager_window = manager_window
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        self.setMinimumHeight(50)
        self.setStyleSheet("QWidget { margin-left: 10px; border-radius: 3px; }")

        font_large = QFont()
        font_large.setFamilies([u"Gotham Pro Black"])
        font_large.setPointSize(14)

        self.account_label = QLabel(self.account_name)
        self.account_label.setFont(font_large)
        layout.addWidget(self.account_label, 4)

        self.checkbox = QCheckBox()
        self.checkbox.setMaximumWidth(28)
        layout.addWidget(self.checkbox, 1)

        self.settings_button = QPushButton("Настроить")
        self.settings_button.setMaximumWidth(100)
        self.settings_button.setStyleSheet("QPushButton { padding: 5px; border-radius: 3px; }")
        layout.addWidget(self.settings_button, 1)
        self.settings_button.clicked.connect(self.show_settings)

        self.delete_account_button = QPushButton("Удалить")
        self.delete_account_button.setMaximumWidth(100)
        self.delete_account_button.setStyleSheet("QPushButton { padding: 5px; border-radius: 3px; }")
        layout.addWidget(self.delete_account_button, 1)
        self.delete_account_button.clicked.connect(self.confirm_delete_account)

        self.setLayout(layout)

    def show_settings(self):
        dialog = AccountSettingsDialog(self.account_id, self.account_name, self.cookies, self.twitch_cookies, self.messages, self.account_proxy,self)
        if dialog.exec() == QDialog.Accepted:
            self.account_name = dialog.account_name_edit.text()
            self.cookies = dialog.cookies_edit.toPlainText()
            self.twitch_cookies = dialog.twitch_cookies_edit.toPlainText() 
            self.messages = dialog.messages_edit.toPlainText()
            self.account_label.setText(self.account_name)

    def confirm_delete_account(self):
        reply = QMessageBox.question(self, 'Confirm Delete', f"Are you sure you want to delete the account '{self.account_name}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.delete_account()

    def delete_account(self):
        user_id = get_user_id()
        if user_id is None:
            QMessageBox.critical(self, "Error", "User ID is not set. Please login again.")
            return

        data = {
            'account_id': self.account_id
        }
        response = requests.post('http://77.232.131.189:5000/delete_kick_account', json=data)
        if response.status_code == 200:
            QMessageBox.information(self, "Success", "Account successfully deleted.")
            self.manager_window.load_accounts() 
        else:
            QMessageBox.critical(self, "Error", "Failed to delete account. Server responded with an error.")
     
class SaveAccountsThread(QThread):
    def __init__(self, user_id, selected_accounts, main_window):
        super().__init__()
        self.user_id = user_id
        self.selected_accounts = selected_accounts
        self.main_window = main_window

    def run(self):
        response = requests.post('http://77.232.131.189:5000/save_selected_accounts', json={'user_id': self.user_id, 'selected_accounts': self.selected_accounts})
        if response.status_code == 200:
            print("Аккаунты успешно сохранены.")
            if self.main_window.streamer_manager:
                for window in self.main_window.streamer_manager.windows.values():
                    window.refresh_accounts()
        else:
            print(f"Failed to save selected accounts. Status code: {response.status_code}")
            print(response.json())
     
class LoadAccountsThread(QThread):
    accounts_loaded = Signal(list)

    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id

    def run(self):
        try:
            response = requests.get('http://77.232.131.189:5000/get_kick_accounts', params={'user_id': self.user_id})
            if response.status_code == 200:
                accounts_data = response.json()
                accounts = accounts_data.get('accounts', [])
                sorted_accounts = sorted(accounts, key=lambda x: x['id'])
                self.accounts_loaded.emit(sorted_accounts)
            else:
                print(f"Failed to load accounts. Status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
     
class AccountManagerWindow(QMainWindow):
    _instance = None

    @staticmethod
    def get_instance():
        if AccountManagerWindow._instance is None:
            AccountManagerWindow._instance = AccountManagerWindow()
        return AccountManagerWindow._instance

    def __init__(self, main_window):
        if AccountManagerWindow._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            super().__init__()
            AccountManagerWindow._instance = self

        self.setWindowTitle("Account Manager")
        self.setGeometry(100, 100, 650, 650)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.main_window = main_window
        self.current_sub_account = 1
        self.sub_account_settings = {str(i): [] for i in range(1, 11)}
        self.old_pos = None

        self.init_ui()
        self.center_on_screen()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        self.setStyleSheet("""
        QWidget {
            background-color: #333;
            color: white;
            margin: 2px;
            border-radius: 3px;
        }
        QPushButton {
            background-color: #555;
            color: white;
            border: 1px solid #666;
            padding: 5px;
            margin: 5px;
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: #777;
        }
        QListWidget {
            background-color: #2b2b2b;
            border: none;
            border-radius: 5px;
        }
        QComboBox {
            background-color: #555;
            color: white;
            border: 1px solid #666;
            padding: 5px;
            margin: 5px;
            border-radius: 5px;
        }
        """)

        self.header = QWidget(self)
        self.header.setFixedHeight(40)
        self.header.setStyleSheet("background-color: #444; border-radius: 5px;")
        layout.addWidget(self.header)

        self.close_button = QPushButton("X", self.header)
        self.close_button.setStyleSheet("QPushButton { color: red; font-weight: bold; border-radius: 5px; }")
        self.close_button.clicked.connect(self.close)
        self.close_button.setGeometry(585, 5, 40, 30)

        # Создаем стековый виджет для наложения анимации на список
        self.stack = QStackedWidget(self.central_widget)
        layout.addWidget(self.stack)

        # Виджет для списка аккаунтов
        self.account_list_widget = QWidget()
        account_list_layout = QVBoxLayout(self.account_list_widget)
        self.account_list = QListWidget()
        account_list_layout.addWidget(self.account_list)
        self.stack.addWidget(self.account_list_widget)
        
        hbox_layout = QHBoxLayout()
        hbox_layout.setContentsMargins(0, 5, 0, 0)
        account_list_layout.addLayout(hbox_layout)
        
        add_account_button = QPushButton("Добавить аккаунт")
        font = QFont()
        font.setFamilies([u"Gotham Pro Black"])
        font.setPointSize(12)
        add_account_button.setFont(font)
        add_account_button.clicked.connect(self.add_account)
        hbox_layout.addWidget(add_account_button, 8)

        self.sub_account_selector = QComboBox()
        self.sub_account_selector.addItems([str(i) for i in range(1, 11)])
        self.sub_account_selector.currentIndexChanged.connect(self.change_sub_account)
        hbox_layout.addWidget(self.sub_account_selector, 1)

        # Виджет для анимации загрузки
        self.loading_widget = QWidget()
        self.loading_layout = QVBoxLayout(self.loading_widget)
        self.loading_layout.setAlignment(Qt.AlignCenter)
        self.loading_label = QLabel(self.loading_widget)
        self.loading_movie = QMovie("images/loading.gif")
        self.loading_label.setMovie(self.loading_movie)
        self.loading_movie.setScaledSize(QtCore.QSize(125, 38))
        self.loading_layout.addWidget(self.loading_label)
        self.stack.addWidget(self.loading_widget)

        self.load_config() 
        self.load_accounts() 

    def load_sub_account_settings_from_server(self):
        user_id = get_user_id()
        if user_id is None:
            print("User ID is not set. Cannot load sub-account settings.")
            return

        try:
            response = requests.get(f'http://77.232.131.189:5000/get_sub_account_settings?user_id={user_id}')
            if response.status_code == 200:
                data = response.json()
                #print(f"Data loaded from server: {data}")
                self.sub_account_settings = data.get('sub_account_settings', {str(i): [] for i in range(1, 11)})
                self.load_sub_account_settings()
                # Устанавливаем текущий индекс в QComboBox после загрузки настроек
                self.sub_account_selector.setCurrentIndex(self.current_sub_account - 1)
            else:
                print("Failed to load sub-account settings")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")

    def save_selected_accounts(self):
        user_id = get_user_id()
        if user_id is None:
            print("User ID is not set. Cannot save selected accounts.")
            return

        selected_accounts = []

        ip_address = self.main_window.ip_address

        for i in range(self.account_list.count()):
            account_widget = self.account_list.itemWidget(self.account_list.item(i))
            if account_widget and account_widget.checkbox.isChecked():
                selected_accounts.append(account_widget.account_id)

        self.sub_account_settings[self.current_sub_account] = selected_accounts

        data = {
            'user_id': user_id,
            'sub_account_settings': {str(k): v for k, v in self.sub_account_settings.items()},
            'ip_address': ip_address
        }

        try:
            #print(f"Data: {data}")
            response = requests.post('http://77.232.131.189:5000/save_sub_account_settings', json=data)
            if response.status_code == 200:
                print("Настройки под-аккаунта сохранены.")
            else:
                print("Failed to save sub-account settings")
                print(response.text)
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")

    def closeEvent(self, event):
        self.save_selected_accounts()
        self.save_config()  # Сохраняем конфигурацию при выходе
        super().closeEvent(event)

    def save_config(self):
        config = {
            'current_sub_account': self.current_sub_account
        }
        with open('config.json', 'w') as f:
            json.dump(config, f)

    def load_config(self):
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.current_sub_account = config.get('current_sub_account', 1)

    def add_account(self):
        dialog = AddAccountDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.load_accounts()

    def load_accounts(self):
        user_id = get_user_id()
        if user_id is None:
            print("User ID is not set. Cannot load accounts.")
            return

        self.account_list.clear()
        self.stack.setCurrentWidget(self.loading_widget)
        self.loading_movie.start()

        self.load_accounts_thread = LoadAccountsThread(user_id)
        self.load_accounts_thread.accounts_loaded.connect(self.on_accounts_loaded)
        self.load_accounts_thread.start()

    @Slot(list)
    def on_accounts_loaded(self, accounts):
        self.loading_movie.stop()
        self.stack.setCurrentWidget(self.account_list_widget)
        for account in accounts:
            self.add_account_to_list(account['id'], account['name'], account['cookies'], account['twitch_cookies'], account['messages'], account['account_proxy'], account['is_selected'])
        self.load_sub_account_settings_from_server()

    def add_account_to_list(self, account_id, name, cookies, twitch_cookies, messages, account_proxy, is_selected):
        account_widget = AccountWidget(account_id, name, cookies, twitch_cookies, messages, account_proxy, self)
        list_widget_item = QListWidgetItem(self.account_list)
        list_widget_item.setSizeHint(account_widget.sizeHint())
        self.account_list.addItem(list_widget_item)
        self.account_list.setItemWidget(list_widget_item, account_widget)
        account_widget.checkbox.setChecked(is_selected)  # Устанавливаем состояние чекбокса

    def change_sub_account(self):
        self.current_sub_account = int(self.sub_account_selector.currentText())
        self.save_config()
        self.load_sub_account_settings()


    def load_sub_account_settings(self):
        selected_accounts = self.sub_account_settings.get(str(self.current_sub_account), [])
        #print(f"Applying settings for sub account {self.current_sub_account}: {selected_accounts}")
        for i in range(self.account_list.count()):
            account_widget = self.account_list.itemWidget(self.account_list.item(i))
            if account_widget:
                #print(f"Account ID: {account_widget.account_id}, Selected: {str(account_widget.account_id) in selected_accounts}")
                account_widget.checkbox.setChecked(str(account_widget.account_id) in selected_accounts)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.header.rect().contains(event.position().toPoint()):
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def center_on_screen(self):
        screen_geometry = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())


# Сервер
class DataFetcherThread(QThread):
    stream_is_start_signal = Signal(str)
    stream_is_over_signal = Signal(str)
    change_streamer_name_signal = Signal(str)
    pochinka_signal = Signal()

    def __init__(self, account_manager, parent=None):
        super(DataFetcherThread, self).__init__(parent)
        self.message_queue = Queue()
        self.parser_started = False
        self.account_manager = account_manager
        self.is_running = True
        self.current_sub_account = None
        self.lead_sub_account()

    def load_config(self):
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.current_sub_account = config.get('current_sub_account', 1)
                
    def run(self):
        last_processed_id = None
        print('DataFetcherThread начал работу.')
        
        while self.is_running:
            try:
                for i in range(50):
                    if not self.is_running:
                        return
                    if i == 1:
                        user_id = get_user_id()
                        self.load_config()
                        sub_account_id = self.current_sub_account
                        params = {'user_id': user_id, 'sub_account_id': sub_account_id}
                        response = requests.get('http://77.232.131.189:5001/get_data', params=params)
                        if response.status_code == 200:
                            data = response.json()
                            message = data.get('message')
                            message_id = data.get('id')
                            if message_id != last_processed_id:
                                last_processed_id = message_id
                                self.message_queue.put((message, message_id))
                        else:
                            print(f'[DataFetcher]: Ошибка при получении данных с сервера')

                        if not self.message_queue.empty():
                            message, _ = self.message_queue.get()
                            message_time = datetime.now()
                            if 'Начался стрим на канале' in message:
                                print(message)
                                split_message = message.split()
                                streamer = split_message[4]
                                # if not self.account_manager.are_drivers_running():
                                #     #self.stream_is_start_signal.emit(streamer)
                                # self.change_streamer_name_signal.emit(streamer)

                            if 'передал рейд' in message:
                                print(message)
                                split_message = message.split()
                                streamer = split_message[3]
                                #self.change_streamer_name_signal.emit(streamer)

                            if 'Стрим на канале' in message:
                                print(message)
                                streamer = message.split()[-2]
                                # if 'Стрим на канале' in message:   
                                #     self.stream_is_over_signal.emit(streamer)

                            if self.account_manager.are_drivers_running():
                                self.account_manager.process_message(message)
                        
                    time.sleep(0.1)

            except Exception as e:
                print(e)

    def lead_sub_account(self):
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.current_sub_account = config.get('current_sub_account', 1)

    def start_parser(self):
        self.parser_started = True
        print("Parser started")

    def stop_parser(self):
        self.parser_started = False
        print("Parser stopped")

    def stop(self):
        self.parser_started = False
        self.is_running = False


# Бот который пишит сообщения
class ChatWriterThread(QThread):
    loaded_signal = Signal()
    send_message_signal = Signal(str)
    wg_active = Signal(bool)
    driver_initialized = Signal(bool)

    def __init__(self, streamer=None, account_name='bot', cookie=None, messages=None, parent=None):
        super(ChatWriterThread, self).__init__(parent)
        self.is_running = True
        self.streamer = streamer
        self.account_name = account_name
        self.cookie = cookie
        self.send_message_signal.connect(self.send_message_on_kick)
        self.wg_active = False
        self.is_ready = False
        self.driver = None
        self.set_streamer_name()
        self.messages = messages if messages else []
        self.all_messages = self.messages.splitlines()
        self.random_messages_enabled = False
        self.raffle_messages_enabled = True
        self.cookie_is_loading = False

        self.sent_messages_file = f"sent_messages/sent_messages_{self.account_name}.txt"
        self.sent_messages = self.load_sent_messages()
        
        self.delay_from = 60
        self.delay_to = 200
        self.load_message_settings()
        
        self.priority_message = None
    
    def load_message_settings(self):
        try:
            with open('message_settings.json', 'r') as file:
                settings = json.load(file)
                self.delay_from = int(settings.get('delay_from', 60))
                self.delay_to = int(settings.get('delay_to', 200))
                self.streamer_name = settings.get('streamer', self.streamer_name)
        except FileNotFoundError:
            print("Файл message_settings.json не найден. Используются значения по умолчанию.")
        except json.JSONDecodeError:
            print("Ошибка при чтении файла message_settings.json. Используются значения по умолчанию.")
             
    def update_streamer_name_in_settings(self):
        try:
            with open('message_settings.json', 'r') as file:
                settings = json.load(file)
            settings['streamer'] = self.streamer_name
            with open('message_settings.json', 'w') as file:
                json.dump(settings, file, indent=4)
            print(f"Имя стримера обновлено в файле: {self.streamer_name}")
        except Exception as e:
            print(f"Ошибка при обновлении имени стримера в файле: {e}")
             
    def set_random_messages_enabled(self, enabled):
        self.random_messages_enabled = enabled
        #print(f'[{self.account_name}] Рандомные сообщения включены: {self.random_messages_enabled}')
    
    def set_raffle_messages_enabled(self, enabled):
        self.raffle_messages_enabled = enabled
        #print(f'[{self.account_name}] Основыные сообщения включены: {self.raffle_messages_enabled}')
    
    @Slot(str)
    def change_streamer_name(self, streamer):
        self.streamer = streamer
        self.set_streamer_name()

    def set_streamer_name(self):
        if self.streamer == 'WatchGamesTV':
            self.streamer_name = 'ibby'
        elif self.streamer == 'Hyuslive':
            self.streamer_name = 'hyus'
        elif self.streamer == 'WRewards':
            self.streamer_name = 'bro'
        elif self.streamer == 'pkle':
            self.streamer_name = 'bro'
        else:
            self.streamer_name = 'bro'
        self.update_streamer_name_in_settings()


    def run(self):
        try:
            self.driver = self.get_chromedriver(
                use_proxy = False,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            if not self.driver:
                return
            
            # self.driver.get('https://pr-cy.ru/browser-details/')
            # time.sleep(1000)
            
            print(f'Окно браузера запущено. [{self.account_name}]')
            site = f'https://kick.com/{self.streamer}'
            #site = f'https://kick.com/Suzuraya1'
            self.driver.get(site)

            self.close_cookies_banner()
            self.add_cookies()
            print(f'Куки добавлены. [{self.account_name}]')
            self.driver.get(site)
            self.check_cookies(site)
            
            while not self.cookie_is_loading:
                print(f'Пытаемя вставить куки ещё раз. [{self.account_name}]')
                self.add_cookies()
                self.check_cookies(site)
                
            self.change_window_title(self.account_name.lower())

            print(f'[{self.account_name}] Готов')
            self.loaded_signal.emit()
            self.driver_initialized.emit(True)

            while self.is_running:
                if self.wg_active and self.raffle_messages_enabled:
                    self.send_message_on_kick('WG')
                    self.wg_active = False
                else:
                    self.check_priority_message()
                    if self.random_messages_enabled:
                        self.load_message_settings()
                        delay = random.randint(self.delay_from, self.delay_to)
                        for i in range(delay):
                            if self.is_running and self.random_messages_enabled:
                                self.check_priority_message()
                                time.sleep(1)
                                if self.wg_active:
                                    break
                            else:
                                break
                        else:
                            self.send_random_message()

                time.sleep(1)

        except Exception as e:
            print(f'Ошибка в методе run() [{self.account_name}] ')
            #print(e)


    def check_priority_message(self):
        if self.priority_message:
            try:
                self.send_message_on_kick(self.priority_message)
                self.priority_message = None
            except Exception as e:
                print(e)
    
    @Slot(str)
    def set_priority_message(self, message):
        self.priority_message = message

    def change_window_title(self, new_title):
        try:
            self.driver.execute_script(f'document.title = "{new_title}"')
        except Exception as e:
            print(f'Ошибка при изменении заголовка окна. {self.account_name}')

    def close_cookies_banner(self):
        wait = WebDriverWait(self.driver, 10)
        banner_is_close = False
        for i in range(5):
            if not banner_is_close:
                try:
                    button2 = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="app"]/span/div/div[3]/button[1]')))
                    button2.click()
                    #print(f'Банер закрыт. [{self.account_name}]')
                    banner_is_close = True
                except Exception as e:
                    print('Не удалось закрыть банер.')
                time.sleep(1)
            else:
                break

    def check_status(self):
        if self.is_running:
            return
        else:
            self.stop()

    def check_cookies(self, site):
        try:
            self.driver.get(site)
            self.avatar_element = self.driver.find_element(By.XPATH, '//*[@id="headlessui-menu-button-3"]/div/img')
            if self.avatar_element:
                self.cookie_is_loading = True
                time.sleep(1)
        except NoSuchElementException:
            print(f'Аватарка не найдена. [{self.account_name}]')
        return False

    def add_cookies(self):
        try:
            cookies = json.loads(self.cookie)
            for cookie in cookies:
                if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                    cookie['sameSite'] = 'None'
                self.driver.add_cookie(cookie)
            #print('Куки успешно добавлены.')
        except Exception as e:
            print(f'Ошибка при добавлении кук: {e}')

    def load_sent_messages(self):
        if os.path.exists(self.sent_messages_file):
            with open(self.sent_messages_file, 'r', encoding='utf-8') as file:
                return file.read().splitlines()
        return []

    def save_sent_message(self, message):
        with open(self.sent_messages_file, 'a', encoding='utf-8') as file:
            file.write(message + '\n')

    def send_random_message(self):
        unsent_messages = [msg for msg in self.all_messages if self.sent_messages.count(msg) < self.all_messages.count(msg)]

        if not unsent_messages:
            self.sent_messages = []
            unsent_messages = self.all_messages
            with open(self.sent_messages_file, 'w', encoding='utf-8') as file:
                file.write('')

        random_message = random.choice(unsent_messages)
        self.send_message_on_kick(random_message.format(streamer_name=self.streamer_name))
        self.save_sent_message(random_message)
        self.sent_messages.append(random_message)

    @Slot(str)
    def send_message_on_kick(self, message):
        if message == 'random' and self.wg_active:
            return
        
        self.chat_input = self.driver.find_element(By.ID, "message-input")

        try:
            if self.chat_input:
                try:
                    if message == 'pochinka':
                        message = '!join'
                        
                    delay = random.randint(1, 10)
                    time.sleep(delay)

                    try:
                        chat_input_text = self.chat_input.text
                        if chat_input_text:
                            print(f'[{self.account_name}] Поле ввода занято, пропускаем сообщение "{message}".')
                            return
                    except Exception:
                        print(f'[{self.account_name}] Ошибка при проверке поля для сообщения.')
                    self.chat_input.click()
                    self.chat_input.send_keys(message)
                    self.chat_input.send_keys(Keys.ENTER)

                    print(f'С аккаунта {self.account_name} отправлено сообщение - {message}')
                except Exception as e:
                    print(f'Ошибка при отправке сообщения [{self.account_name}] ')
                    bring_window_to_front(self.account_name)
            else:
                print(f'Chat input не инициализирован. [{self.account_name}]')
        except Exception as e:
            print(f'Ошибка при поиске chat_input [{self.account_name}] ')


    def get_chromedriver(self, use_proxy, user_agent=None):
        try:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

            if user_agent:
                chrome_options.add_argument(f'--user-agent={user_agent}')
            
            if use_proxy:      
                plugin_file = 'proxy_auth_plugin.zip'

                with zipfile.ZipFile(plugin_file, 'w') as zp:
                    zp.writestr('manifest.json', manifest_json)
                    zp.writestr('background.js', background_js)

                chrome_options.add_extension(plugin_file)

            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument('--ignore-certificate-errors')
            chrome_options.add_argument("--disable-proxy-certificate-handler")
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--allow-running-insecure-content')

            s = Service(executable_path='chromdriver/chromedriver.exe')

            driver = webdriver.Chrome(service=s, options=chrome_options)

            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                'source': '''
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_JSON;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Object;
                    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Proxy;
                '''
            })
            return driver
        except Exception as e:
            print(f'Ошибка при инициализации Chromedriver: {e}')
            return None

    @Slot(bool)
    def set_wg_active(self, state):
        self.wg_active = state

    def stop(self):
        self.is_running = False
        # if self.driver:
        #     try:
        #         self.driver.quit()
        #     except Exception as e:
        #         print(f'Ошибка при закрытии драйвера: {e}')
        print(f'Поток {self.account_name} остановлен')

class StreamerWindowManager:
    def __init__(self):
        self.windows = {}

    def get_window(self, streamer, account_manager):
        if streamer not in self.windows:
            self.windows[streamer] = OnStartAccountManagerWindow(streamer, account_manager)
        return self.windows[streamer]

    def show_window(self, streamer, account_manager):
        window = self.get_window(streamer, account_manager)
        window.showNormal()
        window.bring_to_front()

    def bring_to_front(self, streamer):
        if streamer in self.windows:
            window = self.windows[streamer]
            if window.isMinimized():
                window.showNormal()
            window.raise_()
            window.activateWindow()
            
    def close_all_windows(self):
        for window in self.windows.values():
            window.close()
            
class DriverStateChecker(QThread):
    driver_state_signal = Signal(bool)
    driver_initialization_signal = Signal(bool)

    def __init__(self, chat_writer_thread, parent=None):
        super().__init__(parent)
        self.chat_writer_thread = chat_writer_thread
        self.is_running = True

    def run(self):
        while self.is_running:
            if self.chat_writer_thread and hasattr(self.chat_writer_thread, 'driver') and self.chat_writer_thread.driver:
                try:
                    title = self.chat_writer_thread.driver.title
                    self.driver_state_signal.emit(True)
                except Exception as e:
                    self.driver_state_signal.emit(False)
            else:
                self.driver_state_signal.emit(False)
            self.sleep(5) 

    def stop(self):
        self.is_running = False

class SendMessageDialog(QDialog):
    def __init__(self, parent=None):
        super(SendMessageDialog, self).__init__(parent)
        self.setWindowTitle("Send Message")
        self.setGeometry(100, 100, 400, 150)
        self.center_on_screen()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        font = QFont()
        font2 = QFont()
        font.setPointSize(15)
        font2.setPointSize(12)
        
        self.message_edit = QLineEdit(self)
        self.message_edit.setFont(font)
        self.message_edit.setPlaceholderText("Введите сообщение")
        layout.addWidget(self.message_edit)

        buttons_layout = QHBoxLayout()
        self.send_button = QPushButton("Отправить", self)
        self.cancel_button = QPushButton("Отменить", self)
        self.send_button.setFont(font)
        self.cancel_button.setFont(font)
        buttons_layout.addWidget(self.send_button)
        buttons_layout.addWidget(self.cancel_button)

        self.send_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def get_message(self):
        return self.message_edit.text()
    
    def center_on_screen(self):
        screen_geometry = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

class OnStartAccountWidget(QWidget):
    chat_writer_started = Signal()
    chat_writer_stopped = Signal()

    def __init__(self, streamer, account_name, cookies, twitch_cookies, messages, account_id, parent=None):
        super().__init__(parent)
        self.account_id = account_id
        self.account_name = account_name
        self.cookies = cookies
        self.twitch_cookies = twitch_cookies
        self.messages = messages
        self.streamer = streamer
        self.init_ui()
        self.thread = None
        self.driver_state_checker = None
        self.is_initializing = False

    def init_ui(self):
        layout = QHBoxLayout(self)
        self.setMinimumHeight(50)
        self.setStyleSheet("QWidget { margin-left: 10px; border-radius: 3px; }")

        font_large = QFont()
        font_large.setFamilies([u"Gotham Pro Black"])
        font_large.setPointSize(14)

        self.account_label = QLabel(self.account_name)
        self.account_label.setFont(font_large)
        layout.addWidget(self.account_label, 4)

        self.settings_button = QPushButton("Настроить")
        self.settings_button.setStyleSheet("QPushButton { padding: 5px; border-radius: 3px; }")
        layout.addWidget(self.settings_button, 1)
        self.settings_button.clicked.connect(self.show_settings)

        self.start_chat_writer_button = QPushButton("Запустить")
        self.start_chat_writer_button.setStyleSheet("QPushButton { padding: 5px; border-radius: 3px; }")
        layout.addWidget(self.start_chat_writer_button, 1)
        self.start_chat_writer_button.clicked.connect(self.toggle_chat_writer)

        self.setLayout(layout)

    def show_settings(self):
        dialog = AccountSettingsDialog(self.account_id, self.account_name, self.cookies, self.twitch_cookies, self.messages, self)
        if dialog.exec() == QDialog.Accepted:
            self.account_name = dialog.account_name_edit.text()
            self.cookies = dialog.cookies_edit.toPlainText()
            self.twitch_cookies = dialog.twitch_cookies_edit.toPlainText()
            self.messages = dialog.messages_edit.toPlainText()
            self.account_label.setText(self.account_name)

    def send_message(self, message):
        if self.thread and self.thread.isRunning():
            self.thread.send_message_on_kick(message)

    @Slot()
    def toggle_chat_writer(self):
        if self.thread and self.thread.isRunning():
            self.stop_chat_writer()
        else:
            self.start_chat_writer()

    def start_chat_writer(self):
        if self.thread is None or not self.thread.isRunning():
            self.thread = ChatWriterThread(self.streamer, self.account_name, self.cookies, self.messages)
            self.thread.loaded_signal.connect(self.on_chat_writer_loaded)
            self.thread.driver_initialized.connect(self.on_driver_initialized)
            self.chat_writer_thread = self.thread
            self.thread.start()
            self.is_initializing = True
            self.start_chat_writer_button.setText("Загрузка")
            self.chat_writer_started.emit()
        else:
            print(f'Поток для {self.account_name} уже запущен')

    def stop_chat_writer(self):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.thread.wait()  # Дождаться завершения потока
            self.is_initializing = False
            self.start_chat_writer_button.setText("Запустить")
            #self.chat_writer_stopped.emit()
            self.start_chat_writer_button.setStyleSheet("QPushButton { padding: 5px; border-radius: 3px; }")
            if self.driver_state_checker is not None:
                self.driver_state_checker.stop()

    @Slot()
    def on_chat_writer_loaded(self):
        self.is_initializing = False
        self.start_chat_writer_button.setText("Закрыть")
        self.start_chat_writer_button.setStyleSheet("""
            QPushButton {
                background-color: #810d0d;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #5f0c0c;
            }
        """)
        self.start_driver_state_checker()

    @Slot(bool)
    def on_driver_initialized(self, success):
        if success:
            self.start_chat_writer_button.setText("Закрыть")
        else:
            self.start_chat_writer_button.setText("Запустить")
            self.is_initializing = False
            QMessageBox.critical(self, "Ошибка", "Не удалось инициализировать драйвер. Попробуйте снова.")

    def start_driver_state_checker(self):
        if self.driver_state_checker is None:
            self.driver_state_checker = DriverStateChecker(self.thread)
            self.driver_state_checker.driver_state_signal.connect(self.handle_driver_state)
            self.driver_state_checker.start()

    @Slot(bool)
    def handle_driver_state(self, state):
        if not state and not self.is_initializing:
            self.stop_chat_writer()

    def toggle_random_messages(self, enabled):
        if self.thread and self.thread.isRunning():
            self.thread.set_random_messages_enabled(enabled)

    def toggle_raffle_messages(self, enabled):
        if self.thread and self.thread.isRunning():
            self.thread.set_raffle_messages_enabled(enabled)
        
    def send_priority_message(self, message):
        if self.thread:
            self.thread.set_priority_message(message)
        
    def is_running(self):
        return self.start_chat_writer_button.text() == "Закрыть"
        
class OnStartAccountManagerWindow(QMainWindow):
    def __init__(self, streamer=None, account_manager=None):
        super().__init__()
        self.account_manager = account_manager
        self.streamer = streamer
        self.setWindowTitle(f"Account Manager - {streamer}")
        self.setWindowTitle(streamer)
        self.setGeometry(100, 100, 650, 650)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.init_ui()
        self.old_pos = None
        self.center_on_screen()
        self.chat_writer_threads = []
        self.all_writers_started = False
        self.raffle_messages_enabled = True
        
        self.load_config()
        self.load_sub_account_settings_from_server()
        self.load_accounts()
        
        print(self.current_sub_account)

    def closeEvent(self, event):
        self.hide()
        super().closeEvent(event)
        
    def load_config(self):
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.current_sub_account = config.get('current_sub_account', 1)
                
    def load_sub_account_settings_from_server(self):
        user_id = get_user_id()
        if user_id is None:
            print("User ID is not set. Cannot load sub-account settings.")
            return

        try:
            response = requests.get(f'http://77.232.131.189:5000/get_sub_account_settings?user_id={user_id}')
            if response.status_code == 200:
                data = response.json()
                self.sub_account_settings = data.get('sub_account_settings', {str(i): [] for i in range(1, 11)})
                self.load_sub_account_settings()
            else:
                print("Failed to load sub-account settings")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            
    def load_sub_account_settings(self):
        self.selected_accounts = self.sub_account_settings.get(str(self.current_sub_account), [])
        
    def populate_account_list(self, accounts):
        self.account_list.clear() 
        for account in accounts:
            self.add_account_to_list(account['id'], account['name'], account['cookies'], account['twitch_cookies'], account['messages'])

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)

        self.setStyleSheet("""
        QWidget {
            background-color: #333;
            color: white;
            margin: 2px;
            border-radius: 3px;
        }
        QPushButton {
            background-color: #555;
            color: white;
            border: 1px solid #666;
            padding: 5px;
            margin: 5px;
            border-radius: 5px;
        }
        QPushButton:hover {
            background-color: #777;
        }
        QListWidget {
            background-color: #2b2b2b;
            border: none;
            border-radius: 5px;
        }
        """)

        self.header = QWidget(self)
        self.header.setFixedHeight(40)
        self.header.setStyleSheet("background-color: #444; border-radius: 5px;")
        layout.addWidget(self.header)

        self.close_button = QPushButton("X", self.header)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #810d0d;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5f0c0c;
            }
        """)
        self.close_button.clicked.connect(self.close)
        self.close_button.setGeometry(585, 5, 40, 30)
        
        self.minimize_button = QPushButton("-", self.header)
        self.minimize_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        self.minimize_button.clicked.connect(self.showMinimized)
        self.minimize_button.setGeometry(545, 5, 40, 30)

        self.account_list = QListWidget()
        self.account_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #2a2a2a;
            }
        """)
        layout.addWidget(self.account_list)
        
        font = QFont()
        font.setPointSize(12)

        self.start_all_writers_button = QPushButton("Запустить все")
        self.start_all_writers_button.setFont(font)
        self.start_all_writers_button.setCheckable(True)
        self.start_all_writers_button.setChecked(False)
        self.start_all_writers_button.clicked.connect(self.toggle_start_all_writers)
        self.start_all_writers_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border-radius: 5px;
                margin-bottom: 5px;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        layout.addWidget(self.start_all_writers_button)


        hbox_layout = QHBoxLayout()
        hbox_layout.setContentsMargins(0, 5, 0, 0)
        layout.addLayout(hbox_layout)
    

        self.toggle_random_messages_button = QPushButton("Включить рандомные сообщения", self)
        self.toggle_random_messages_button.setFont(font)
        self.toggle_random_messages_button.setCheckable(True)
        self.toggle_random_messages_button.setChecked(False)
        self.toggle_random_messages_button.clicked.connect(self.toggle_random_messages)
        self.toggle_random_messages_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border-radius: 5px;
                margin-bottom: 5px;
                margin-top: 0px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        #layout.addWidget(self.toggle_random_messages_button)
        hbox_layout.addWidget(self.toggle_random_messages_button, 5)
        
        self.raffle_message_control_button = QtWidgets.QPushButton("Выключить основные сообщения", self)
        self.raffle_message_control_button.setFont(font)
        self.raffle_message_control_button.setCheckable(True)
        self.raffle_message_control_button.setChecked(True)  # По умолчанию отправка разрешена
        self.raffle_message_control_button.clicked.connect(self.toggle_message_sending)
        self.raffle_message_control_button.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border-radius: 5px;
                margin-bottom: 5px;
                margin-top: 0px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        #layout.addWidget(self.raffle_message_control_button)
        hbox_layout.addWidget(self.raffle_message_control_button, 5)
        
        self.message_dialog_button = QtWidgets.QPushButton("Массовая рассылка сообщения", self)
        self.message_dialog_button.setFont(font)
        self.message_dialog_button.clicked.connect(self.open_send_message_dialog)
        layout.addWidget(self.message_dialog_button)

    def open_send_message_dialog(self):
        dialog = SendMessageDialog(self)
        if dialog.exec() == QDialog.Accepted:
            message = dialog.get_message()
            self.send_message_to_all_drivers(message)
            
    def send_message_to_all_drivers(self, message):
        for index in range(self.account_list.count()):
            item = self.account_list.item(index)
            widget = self.account_list.itemWidget(item)
            widget.send_priority_message(message)

    def refresh_accounts(self):
        self.load_accounts()

    def toggle_random_messages(self):
        self.random_messages_enabled = self.toggle_random_messages_button.isChecked()
        if self.random_messages_enabled:
            for index in range(self.account_list.count()):
                item = self.account_list.item(index)
                widget = self.account_list.itemWidget(item)
                widget.toggle_random_messages(True)
            self.toggle_random_messages_button.setText("Выключить рандомные сообщения")
            print(f'Рандомные сообщения включены: {self.random_messages_enabled}')
        else:
            for index in range(self.account_list.count()):
                item = self.account_list.item(index)
                widget = self.account_list.itemWidget(item)
                widget.toggle_random_messages(False)
            self.toggle_random_messages_button.setText("Включить рандомные сообщения") 
            print(f'Рандомные сообщения включены: {self.random_messages_enabled}')
 
    def toggle_message_sending(self):
        self.raffle_messages_enabled = self.raffle_message_control_button.isChecked()
        self.account_manager.set_wg_pochinka_enabled(self.raffle_messages_enabled)
        if self.raffle_messages_enabled:
            for index in range(self.account_list.count()):
                item = self.account_list.item(index)
                widget = self.account_list.itemWidget(item)
                widget.toggle_raffle_messages(True)
            self.raffle_message_control_button.setText("Выключить WG и pochinka сообщения")
            print(f'Основные сообщения включены: {self.raffle_messages_enabled}')
        else:
            for index in range(self.account_list.count()):
                item = self.account_list.item(index)
                widget = self.account_list.itemWidget(item)
                widget.toggle_raffle_messages(False)
            self.raffle_message_control_button.setText("Включить WG и pochinka сообщения")
            print(f'Основные сообщения включены: {self.raffle_messages_enabled}')
 
    def toggle_start_all_writers(self):
        self.all_writers_started = self.start_all_writers_button.isChecked()
        if self.all_writers_started:
            self.start_all_writers_button.setText('Закрыть все')
            self.start_all_writers()
        else:
            self.start_all_writers_button.setText('Запустить все')
            self.kill_all_chrome_processes()

    def start_all_writers(self):
        for index in range(self.account_list.count()):
            item = self.account_list.item(index)
            widget = self.account_list.itemWidget(item)
            widget.toggle_chat_writer()
            
    def kill_all_chrome_processes(self):
        for process in psutil.process_iter(['pid', 'name']):
            if 'chrome' in process.info['name'].lower():
                try:
                    p = psutil.Process(process.info['pid'])
                    p.kill()
                except psutil.NoSuchProcess:
                    pass

    def load_accounts(self):
        user_id = get_user_id()
        if user_id is None:
            print("User ID is not set. Cannot load accounts.")
            return

        self.account_list.clear() 

        try:
            ip_address = requests.get('https://api.ipify.org').text
            response = requests.get('http://77.232.131.189:5000/get_selected_accounts', params={'user_id': user_id, 'ip_address': ip_address})
            if response.status_code == 200:
                accounts_data = response.json()
                accounts = accounts_data.get('accounts', [])
                sorted_accounts = sorted(accounts, key=lambda x: x['id'])
                for account in sorted_accounts:
                    #print(f'{account['id']}', self.selected_accounts)
                    if f"{account['id']}" in self.selected_accounts:
                        self.add_account_to_list(account['id'], account['name'], account['cookies'], account['twitch_cookies'], account['messages'])
            else:
                print(f"Failed to load accounts. Status code: {response.status_code}")
                print(response.json())
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")

    def add_account_to_list(self, account_id, name, cookies, twitch_cookies, messages):
        account_widget = OnStartAccountWidget(self.streamer, name, cookies, twitch_cookies, messages, account_id, self)
        account_widget.chat_writer_started.connect(self.account_manager.on_chat_writer_started)
        account_widget.chat_writer_stopped.connect(self.account_manager.on_chat_writer_stopped)
        list_widget_item = QListWidgetItem(self.account_list)
        list_widget_item.setSizeHint(account_widget.sizeHint())
        self.account_list.addItem(list_widget_item)
        self.account_list.setItemWidget(list_widget_item, account_widget)
        self.account_manager.add_account_widget(account_widget)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.header.rect().contains(event.position().toPoint()):
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.old_pos is not None:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def center_on_screen(self):
        screen_geometry = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def bring_to_front(self):
        self.raise_()
        self.activateWindow()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setWindowTitle("Настройки")
        self.setGeometry(100, 100, 500, 270)
        self.setMinimumSize(400, 200)
        self.init_ui()
        self.load_settings()
        self.center_on_screen()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QDialog {
                background-color: #333;
                color: white;
            }
            QLabel {
                margin-top: 5px;
            }
            QLineEdit,  QComboBox {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
                padding: 5px;
                margin-top: 5px;
                margin-bottom: 5px;
                border-radius: 5px;
                min-height: 15px;
            }
            QTextEdit {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
                padding: 5px;
                margin-top: 5px;
                margin-bottom: 5px;
                border-radius: 5px;
                min-height: 60px;
            }
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #666;
                padding: 5px;
                margin: 5px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        
        font = QFont()
        font2 = QFont()
        font.setPointSize(15)
        font2.setPointSize(18)

        self.delay_label = QLabel("Введите задержку для рандомных сообщений:")
        self.delay_label.setFont(font)
        layout.addWidget(self.delay_label)

        delay_layout = QHBoxLayout()
        self.delay_input_from = QLineEdit()
        self.delay_input_from.setPlaceholderText("От")
        self.delay_input_from.setMaxLength(5)
        self.delay_input_from.setFont(font)
        delay_layout.addWidget(self.delay_input_from)

        self.delay_input_to = QLineEdit()
        self.delay_input_to.setPlaceholderText("До")
        self.delay_input_to.setMaxLength(5)
        self.delay_input_to.setFont(font)
        delay_layout.addWidget(self.delay_input_to)
        layout.addLayout(delay_layout)

        self.streamer_label = QLabel("Выберите имя стримера:")
        self.streamer_label.setFont(font)
        self.streamer_combo = QComboBox()
        self.streamer_combo.addItems(["ibby", "pkle", "hyus", "maxim", "sam", "henny", "bro", "coolbreez"])
        self.streamer_combo.setFont(font)
        layout.addWidget(self.streamer_label)
        layout.addWidget(self.streamer_combo)

        # self.default_message_label = QLabel("Введите дефолтные сообщения:")
        # self.default_message_label.setFont(font)
        # self.default_message_input = QTextEdit()
        # self.default_message_input.setFont(font)
        # layout.addWidget(self.default_message_label)
        # layout.addWidget(self.default_message_input)

        self.save_button = QPushButton("Сохранить")
        self.save_button.setFont(font2)
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

    def save_settings(self):
        settings = {
            'delay_from': self.delay_input_from.text(),
            'delay_to': self.delay_input_to.text(),
            'streamer': self.streamer_combo.currentText(),
        }
        with open('message_settings.json', 'w') as file:
            json.dump(settings, file, indent=4)
        print(f"Настройки сохранены: {settings}")
        self.accept()

    def load_settings(self):
        if os.path.exists('message_settings.json'):
            with open('message_settings.json', 'r') as file:
                settings = json.load(file)
                self.delay_input_from.setText(settings.get('delay_from', ''))
                self.delay_input_to.setText(settings.get('delay_to', ''))
                self.streamer_combo.setCurrentText(settings.get('streamer', 'Streamer1'))
                #self.default_message_input.setPlainText(settings.get('default_messages', ''))
                #print(f"Настройки загружены: {settings}")

    def center_on_screen(self):
        screen_geometry = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

# Главное окно
class MainApp(QMainWindow):
    def __init__(self):
        super(MainApp, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        normal_cursor_path = 'cursor/Glib Cur v3 (Rounded)/Normal Select.cur'
        normal_cursor_pixmap = QtGui.QPixmap(normal_cursor_path)
        normal_cursor = QtGui.QCursor(normal_cursor_pixmap, 0, 0)
        self.setCursor(normal_cursor)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.size())
        self.old_pos = self.pos()

        self.ui.login_error_text.hide()
        self.ui.close_button.clicked.connect(self.close_button_act)
        self.ui.wrap_button.clicked.connect(self.wrap_button_act)
        self.ui.login_button.clicked.connect(self.check_login)
        self.ui.pass_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.add_buttons_style()

        self.show_login_frame()

        self.ui.hyus_icon = self.wrap_with_frame(self.ui.hyus_icon, "images/hyus.png")
        self.ui.pkle_icon = self.wrap_with_frame(self.ui.pkle_icon, "images/pkle.png")
        self.ui.wrewards_icon = self.wrap_with_frame(self.ui.wrewards_icon, "images/wrewards.png")
        self.ui.ibby_icon = self.wrap_with_frame(self.ui.ibby_icon, "images/ibby.png")

        self.streamer = None
        self.streamer_frames = [self.ui.hyus_icon, self.ui.pkle_icon, self.ui.wrewards_icon, self.ui.ibby_icon]
        self.ui.hyus_icon.clicked.connect(lambda: self.change_streamer('Hyuslive'))
        self.ui.pkle_icon.clicked.connect(lambda: self.change_streamer('pkle'))
        self.ui.wrewards_icon.clicked.connect(lambda: self.change_streamer('WRewards'))
        self.ui.ibby_icon.clicked.connect(lambda: self.change_streamer('WatchGamesTV'))

        self.ui.start_button.clicked.connect(self.start_button_act)
        self.show_login_frame()

        self.credentials_file = 'credentials.json'
        if self.load_credentials():
            print("Пропускаю дальше")
            self.show_main_menu()
        else:
            print('Надо залогиниться')
            
        self.ip_address = self.get_ip_address()

        self.settings_window = None
        self.account_manager_window = None
        self.on_start_account_manager_window = None
        self.shop_parser_window = None
        self.calendar_parser_window = None

        self.threads = None
        self.streamer_manager = StreamerWindowManager()

        self.data_fetcher_thread = DataFetcherThread(None, self)
        self.account_manager = AccountManager(self.data_fetcher_thread)
        self.data_fetcher_thread.account_manager = self.account_manager
        

        self.data_fetcher_thread.stream_is_start_signal.connect(self.stream_is_start)
        self.data_fetcher_thread.stream_is_over_signal.connect(self.stop_all_drivers)
        self.data_fetcher_thread.change_streamer_name_signal.connect(self.change_streamer_name)
        self.data_fetcher_thread.start()
        
        self.ui.item_messages.clicked.connect(self.open_settings)
        self.default_delay = None
        self.default_streamer = None
        self.default_messages = None
        
        self.ui.item_accounts.clicked.connect(self.open_account_manager)
        self.ui.item_shop.clicked.connect(self.open_shop_parser)
        self.ui.item_calendar.clicked.connect(self.open_calendar_parser)
        
        self.apply_hover_styles()
        
        
    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.default_delay_from = dialog.delay_input_from.text()
            self.default_delay_to = dialog.delay_input_to.text()
            self.default_streamer = dialog.streamer_combo.currentText()
            self.default_messages = dialog.default_message_input.toPlainText()
            self.apply_settings()

    def apply_settings(self):
        print(f"Настройки применены: Задержка: от {self.default_delay_from} до {self.default_delay_to}, Стример: {self.default_streamer}, Дефолтные сообщения: {self.default_messages}")
        
    def open_shop_parser(self):
        if self.shop_parser_window is None:
            self.shop_parser_window = ShopParserWindow()
        self.shop_parser_window.show()
        self.shop_parser_window.raise_()
        self.shop_parser_window.activateWindow()
        if self.shop_parser_window.isMinimized():
                self.shop_parser_window.showNormal()
        
    def open_calendar_parser(self):
        if self.calendar_parser_window is None:
            self.calendar_parser_window = CalendarParserWindow()
        self.calendar_parser_window.show()
        self.calendar_parser_window.raise_()
        self.calendar_parser_window.activateWindow()
        if self.calendar_parser_window.isMinimized():
                self.calendar_parser_window.showNormal()

    def open_account_manager(self):
        if self.account_manager_window is None:
            self.account_manager_window = AccountManagerWindow(self)
        self.account_manager_window.show()
        self.account_manager_window.raise_()
        self.account_manager_window.activateWindow()
        if self.account_manager_window.isMinimized():
                self.account_manager_window.showNormal()

    def start_button_act(self):
        if self.streamer is not None:
            self.ui.start_button_error_text.hide()
            print(self.streamer)
            self.streamer_manager.show_window(self.streamer, self.account_manager)
        else:
            self.ui.start_button_error_text.show()

    @Slot(str)
    def stream_is_start(self, streamer):
        self.change_streamer(streamer)
        self.on_start_account_manager_window = OnStartAccountManagerWindow(self.streamer, self.account_manager)
        self.on_start_account_manager_window.show()
        self.on_start_account_manager_window.start_all_writers()
        
    @Slot(str)
    def stop_all_drivers(self, streamer):
        print(f"Получен сигнал о завершении стрима для {streamer}. Останавливаем все драйверы.")
        #for widget in self.account_manager.account_widgets:
            #if widget.thread and widget.thread.isRunning():
                #widget.thread.stop()
        #self.kill_all_chrome_processes()
                
    def kill_all_chrome_processes(self):
        for process in psutil.process_iter(['pid', 'name']):
            if 'chrome' in process.info['name'].lower():
                try:
                    p = psutil.Process(process.info['pid'])
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
            
            
    @Slot(str)
    def change_streamer_name(self, streamer):
        print(f"Стрим на канале {self.streamer} закончился, меняем имя стримера на {streamer}.")
        for widget in self.account_manager.account_widgets:
            if widget.thread and widget.thread.isRunning():
                widget.thread.change_streamer_name(streamer)

    def replace_with_clickable(self, label, image_path):
        clickable_label = ClickableLabel(label.parent())
        clickable_label.setGeometry(label.geometry())
        clickable_label.setPixmap(QtGui.QPixmap(image_path))
        clickable_label.setScaledContents(True)
        clickable_label.setAlignment(label.alignment())
        clickable_label.setFrameShape(label.frameShape())
        clickable_label.setObjectName(label.objectName())
        label.deleteLater()
        return clickable_label
    
    def wrap_with_frame(self, label, image_path):
        frame = ClickableFrame(label.parent())
        frame.setGeometry(label.geometry())
        frame.setObjectName(label.objectName())
        frame.setStyleSheet("background: transparent; padding: 2px;")

        frame.label.setGeometry(0, 0, label.width(), label.height())
        frame.label.setPixmap(QtGui.QPixmap(image_path))
        frame.label.setScaledContents(True)
        frame.label.setAlignment(label.alignment())
        frame.label.setFrameShape(label.frameShape())

        return frame
    
    def change_streamer(self, streamer):
        if streamer == 'Hyuslive':
            frame = self.ui.hyus_icon
        if streamer == 'pkle':
            frame = self.ui.pkle_icon
        if streamer == 'WRewards':
            frame = self.ui.wrewards_icon
        if streamer == 'WatchGamesTV':
            frame = self.ui.ibby_icon
            
        self.streamer = streamer
            
        for f in self.streamer_frames:
            f.setGraphicsEffect(None)
        shadow = QGraphicsDropShadowEffect(frame)
        shadow.setBlurRadius(10)
        shadow.setColor(Qt.white)
        shadow.setOffset(0, 0)
        frame.setGraphicsEffect(shadow)
 
    def show_login_frame(self):
        self.ui.item_accounts.hide()
        self.ui.item_calendar.hide()
        self.ui.item_devices.hide()
        self.ui.item_messages.hide()
        self.ui.item_shop.hide()
        self.ui.item_points.hide()
        self.ui.hyus_border.hide()
        self.ui.hyus_icon.hide()
        self.ui.pkle_border.hide()
        self.ui.pkle_icon.hide()
        self.ui.wrewards_border.hide()
        self.ui.wrewards_icon.hide()
        self.ui.ibby_border.hide()
        self.ui.ibby_icon.hide()
        self.ui.wrap_button_2.hide()
        self.ui.wrap_button_3.hide()
        self.ui.start_button_error_text.hide()
        self.ui.start_button.hide()
        
    def check_logged_in(self):
        try:
            with open('credentials.json', 'r') as file:
                credentials = json.load(file)
                if credentials.get('login') and credentials.get('password'):
                    return True
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return False
    
    def check_login(self):
        login = self.ui.login_input.text()
        password = self.ui.pass_input.text()
        self.login_server_response(login, password)
    
    def load_credentials(self):
        try:
            with open(self.credentials_file, 'r') as file:
                credentials = json.load(file)
                login = credentials['username']
                password = credentials['password']
                self.login_server_response(login, password)
                return True
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
    def save_credentials(self, username, password, user_id):
        with open(self.credentials_file, 'w') as file:
            json.dump({'username': username, 'password': password, 'user_id': user_id}, file)
            
    def login_server_response(self, login, password):
        response = requests.post('http://77.232.131.189:5000/check_login', json={'login': login, 'password': password})
        if response.status_code == 200:
            data = response.json()
            if data.get('result'):
                global current_user_id
                current_user_id = data.get('user_id') 
                print(current_user_id)
                self.ui.login_error_text.hide()
                print("Login successful!")
                self.save_credentials(login, password, current_user_id)
                self.show_main_menu()
            else:
                self.ui.login_error_text.show()
                print("Login failed!")
        else:
            QMessageBox.critical(self, "Login Error", "Failed to connect to the server.")
            
    def delete_credentials(self):
        try:
            os.remove(self.credentials_file)
        except OSError:
            pass

    def show_main_menu(self):
        self.ui.login_frame.hide()
        self.ui.login_error_text.hide()
        
        self.ui.item_accounts.show()
        self.ui.item_calendar.show()
        self.ui.item_devices.show()
        self.ui.item_messages.show()
        self.ui.item_shop.show()
        self.ui.item_points.show()
        self.ui.hyus_icon.show()
        self.ui.pkle_icon.show()
        self.ui.wrewards_icon.show()
        self.ui.ibby_icon.show()
        self.ui.wrap_button_2.show()
        self.ui.wrap_button_3.show()
        self.ui.start_button.show()
        
    def add_buttons_style(self):
        self.ui.login_button.setStyleSheet("""
            QPushButton {
                background: #ffd17a;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #ffc048;
            }
        """)
        
        self.ui.start_button.setStyleSheet("""
            QPushButton {
                background: #ffae00;
                border-radius: 5px;
                color: white;
            }
            QPushButton:hover {
                background: #d79300;
            }
        """) 

    def apply_hover_styles(self):
        items = [self.ui.item_accounts, self.ui.item_calendar, self.ui.item_devices,
                 self.ui.item_messages, self.ui.item_shop, self.ui.item_points]

        stylesheet = """
            QPushButton {
                color: white;
                text-align: left;
            }
            QPushButton:hover {
                color: #ffa800;
                margin-left: 5px;
            }
        """

        for item in items:
            item.setStyleSheet(stylesheet)
        
    def get_ip_address(self):
        try:
            return requests.get('https://api.ipify.org').text
        except requests.RequestException as e:
            print(f"Error getting IP address: {e}")
            return None
        
    def mousePressEvent(self, event):
            if event.buttons() == Qt.LeftButton:
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
    
    def close_button_act(self):
        self.close()      
    
    def wrap_button_act(self):
        self.showMinimized()
        
    def closeEvent(self, event):
        if hasattr(self, 'account_manager_window'):
            if self.account_manager_window:
                self.account_manager_window.close()
        if hasattr(self, 'on_start_account_manager_window'):
            if self.on_start_account_manager_window:
                self.on_start_account_manager_window.close()
        if hasattr(self, 'calendar_parser_window'):
            if self.calendar_parser_window:
                self.calendar_parser_window.close()
        if hasattr(self, 'streamer_manager'):
            if self.streamer_manager:
                self.streamer_manager.close_all_windows()
        if hasattr(self, 'data_fetcher_thread'):
            if self.data_fetcher_thread:
                self.data_fetcher_thread.stop()
                self.data_fetcher_thread.wait()
        event.accept()
        

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    
    sys.exit(app.exec())