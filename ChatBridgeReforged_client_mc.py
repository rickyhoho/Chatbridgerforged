import json
import os
import socket as soc
import struct
import threading
import time
import traceback

from binascii import b2a_hex, a2b_hex
from Crypto.Cipher import AES
from datetime import datetime

from mcdreforged.api.all import *

debug_mode = False
ping_time = 60
timeout = 120
config_path = 'config/ChatBridgeReforged_client.json'
log_path = 'logs/ChatBridgeReforged_Client_mc.log'
client = None
prefix = '!!CBR'
prefix2 = '!!cbr'
client_color = '6'  # minecraft color code
CLIENT_TYPE = "mc"
LIB_VERSION = "v20210820"


def rtext_cmd(txt, msg, cmd):
    return RText(txt).h(msg).c(RAction.run_command, cmd)


def help_formatter(mcdr_prefix, command, first_msg, click_msg, use_command=None):
    if use_command is None:
        use_command = command
    msg = f'{mcdr_prefix} {command} §a{first_msg}'
    return rtext_cmd(msg, f'Click me to {click_msg}', f'{mcdr_prefix} {use_command}')


help_msg = '''§b-----------§fChatBridgeReforged_Client§b-----------§r
''' + help_formatter(prefix, 'help', 'show help message§r', 'show help message') + '''
''' + help_formatter(prefix, 'start', 'start ChatBridgeReforged client§r', 'start') + '''
''' + help_formatter(prefix, 'stop', 'stop ChatBridgeReforged client§r', 'stop') + '''
''' + help_formatter(prefix, 'status', 'show status of ChatBridgeReforged client§r', 'show status') + '''
''' + help_formatter(prefix, 'reload', 'reload ChatBridgeReforged client§r', 'reload') + '''
''' + help_formatter(prefix, 'restart', 'restart ChatBridgeReforged client§r', 'restart') + '''
''' + help_formatter(prefix, 'ping', 'ping ChatBridgeReforged server§r', 'ping') + '''
§b-----------------------------------------------§r'''

PLUGIN_METADATA = {
    'id': 'chatbridgereforged_client_mc',
    'version': '0.0.1-Beta-013',
    'name': 'ChatBridgeReforged_Client_mc',
    'description': 'Reforged of ChatBridge, Client for normal mc server.',
    'author': 'ricky',
    'link': 'https://github.com/rickyhoho/ChatBridgeReforged',
    'dependencies': {
        'mcdreforged': '>=1.3.0'
    }
}

DEFAULT_CONFIG = {
    "name": "survival",
    "password": "survival",
    "host_name": "127.0.0.1",
    "host_port": 30001,
    "aes_key": "ThisIsTheSecret"
}


def out_log(msg: str, error=False, debug=False, not_spam=False):
    for i in range(6):
        msg = msg.replace('§' + str(i), '').replace('§' + chr(97 + i), '')
    msg = msg.replace('§6', '').replace('§7', '').replace('§8', '').replace('§9', '')
    heading = '[CBR] ' + datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
    if error:
        msg = heading + '[ERROR]: ' + msg
    elif debug:
        if not debug_mode:
            return
        msg = heading + '[DEBUG]: ' + msg
    else:
        msg = heading + '[INFO]: ' + msg
    if not not_spam:
        print(msg + '\n', end='')
    with open(log_path, 'a+') as log:
        log.write(msg + '\n')


def bug_log(error=False):
    print('[CBR] bug exist')
    for bug in traceback.format_exc().splitlines():
        if error:
            out_log(bug, error=True)
        else:
            out_log(bug, debug=True)


def print_msg(msg, num, info=None, server: ServerInterface = None, player='', error=False, debug=False, not_spam=False):
    if num == 0:
        if server is not None:
            if player == '':
                server.say(msg)
            else:
                server.tell(player, msg)
        out_log(str(msg), not_spam=not_spam)
    elif num == 1:
        server.reply(info, msg)
        out_log(str(msg))
    elif num == 2:
        if info is None or not info.is_player:
            out_log(msg, error, debug)
        else:
            server.reply(info, msg)


def load_config():
    sync = False
    if not os.path.exists(log_path):
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        out_log('Log file not find', error=True)
        out_log('Generate new log file')

    if not os.path.exists(config_path):
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        out_log('Config not find', error=True)
        out_log('Generate default config')
        with open(config_path, 'w') as config_file:
            json.dump(DEFAULT_CONFIG, config_file, indent=4)
        return DEFAULT_CONFIG
    with open(config_path, 'r') as config_file:
        data = dict(json.load(config_file))
    for keys in DEFAULT_CONFIG.keys():
        if keys not in data.keys():
            out_log(f"Config {keys} not found, use default value {DEFAULT_CONFIG[keys]}", error=True)
            data.update({keys: DEFAULT_CONFIG[keys]})
            sync = True
    if sync:
        with open(config_path, 'w') as config_file:
            json.dump(data, config_file, indent=4)
    return data


class AESCryptor:
    # key and text needs to be utf-8 str in python2 or str in python3
    # by ricky, most of the code keep cause me dose not want to change this part
    def __init__(self, key, mode=AES.MODE_CBC):
        self.key = self.__to16length(key)
        self.mode = mode

    def __to16length(self, text):
        text = bytes(text, encoding="utf-8")
        return text + (b'\0' * ((16 - (len(text) % 16)) % 16))

    def encrypt(self, text):
        cryptor = AES.new(self.key, self.mode, self.key)
        text = self.__to16length(text)
        result = b2a_hex(cryptor.encrypt(text))
        result = str(result, encoding='utf-8')
        return result

    def decrypt(self, text):
        cryptor = AES.new(self.key, self.mode, self.key)
        text = bytes(text, encoding='utf-8')
        try:
            result = cryptor.decrypt(a2b_hex(text))
        except TypeError as err:
            out_log('TypeError when decrypting text', True)
            out_log('text =' + str(text), True)
            raise err
        except ValueError as err:
            out_log(str(err.args), True)
            out_log('len(text) =' + str(len(text)), True)
            raise err
        try:
            result = str(result, encoding='utf-8')
        except UnicodeDecodeError:
            out_log('error at decrypt string conversion', True)
            out_log('raw result = ' + str(result), True)
            result = str(result, encoding='ISO-8859-1')
            out_log('ISO-8859-1 = ' + str(result), True)
        return result.rstrip('\0')


class Network(AESCryptor):
    def __init__(self, key):
        super().__init__(key)
        self.connected = False

    def receive_msg(self, socket: soc.socket, address):
        data = socket.recv(4)
        if len(data) < 4:
            return '{}'
        length = struct.unpack('I', data)[0]
        msg = socket.recv(length)
        msg = str(msg, encoding='utf-8')
        try:
            msg = self.decrypt(msg)
        except Exception:
            return '{}'
        out_log(f"Received {msg!r} from {address!r}", debug=True)
        return msg

    def send_msg(self, socket: soc.socket, msg, target=''):
        if not client.connected:
            out_log("Not connected to the server", debug=True)
            return
        if target != '':
            target = 'to ' + target
        out_log(f"Send: {msg!r} {target}", debug=True)
        msg = self.encrypt(msg)
        msg = bytes(msg, encoding='utf-8')
        msg = struct.pack('I', len(msg)) + msg
        try:
            socket.sendall(msg)
        except BrokenPipeError:
            out_log("Connection closed from server")
            client.connected = False
            client.close_connection()


class ClientProcess:
    def __init__(self, client_class: 'CBRTCPClient'):
        self.client = client_class
        self.end = 0

    def message_formatter(self, client_name, player, msg):
        if player != "":
            message = f"§7[§{client_color}{client_name}§7] <{player}> {msg}"  # chat message
        else:
            message = f"§7[§{client_color}{client_name}§7] {msg}"
        return message

    def msg_json_formatter(self, client_name, player, msg):
        message = {
            "action": "message",
            "client": client_name,
            "player": player,
            "message": msg
        }
        return json.dumps(message)

    def ping_test(self):
        if not self.client.connected:
            return -2
        out_log(f'Ping to server', debug=True)
        start_time = time.time()
        self.client.send_msg(self.client.socket, '{"action": "keepAlive", "type": "ping"}', 'server')
        self.ping_result()
        out_log(f'get ping result from server', debug=True)
        if self.end == -1:
            out_log(f'No response from server', debug=True)
            return -1
        return round((self.end - start_time) * 1000, 1)

    def ping_result(self):
        self.end = 0
        start = time.time()
        while time.time() - start <= 2:
            if self.end != 0:
                return
        self.end = -1

    def ping_log(self, ping_ms, info=None, server=None):
        if ping_ms == -2:
            print_msg(f'- Offline', 2, info, server=server)
        elif ping_ms == -1:
            print_msg(f'- No response - time = 2000ms', 2, info, server=server)
        else:
            print_msg(f'- Alive - time = {ping_ms}ms', 2, info, server=server)

    def process_msg(self, msg, socket: soc.socket):
        if 'action' in msg.keys():
            if msg['action'] == 'result':
                if msg['result'] == 'login success':
                    out_log("Login Success")
                else:
                    out_log("Login in fail", error=True)
            elif msg['action'] == 'keepAlive':
                if msg['type'] == 'ping':
                    self.client.send_msg(socket, '{"action": "keepAlive", "type": "pong"}')
                elif msg['type'] == 'pong':
                    self.end = time.time()
            elif msg['action'] == 'message':
                for i in msg['message'].splitlines():
                    message = self.message_formatter(msg['client'], msg['player'], i)
                    print_msg(message, num=0, player=msg['receiver'], server=self.client.server, not_spam=True)
            elif msg['action'] == 'stop':
                self.client.close_connection()
                out_log(f'Connection closed from server')
            elif msg['action'] == 'command':
                command = msg['command']
                msg['result']['responded'] = True
                if self.client.server is not None and self.client.server.is_rcon_running():
                    result = self.client.server.rcon_query(command)
                    print(result)
                    if result is not None:
                        msg['result']['type'] = 0
                        msg['result']['result'] = result
                    else:
                        msg['result']['type'] = 1
                else:
                    msg['result']['type'] = 2
                self.client.send_msg(socket, json.dumps(msg))


class CBRTCPClient(Network):
    def __init__(self, config_data):
        super().__init__(config_data['aes_key'])
        self.ip = config_data['host_name']
        self.port = config_data['host_port']
        self.name = config_data['name']
        self.password = config_data['password']
        self.server = None
        self.socket = None
        self.connected = False
        self.cancelled = False
        self.process = ClientProcess(self)

    def setup(self, config_data):
        super().__init__(config_data['aes_key'])
        self.ip = config_data['host_name']
        self.port = config_data['host_port']
        self.name = config_data['name']
        self.password = config_data['password']
        self.connected = False
        self.cancelled = False

    def try_start(self, info=None):
        if not self.connected:
            threading.Thread(target=self.start, name='CBR', args=(info,), daemon=True).start()
        else:
            if info is not None:
                print_msg("Already Connected to server", 2, info, server=self.server, error=True)
            else:
                out_log("Already Connected to server", debug=True)

    def start(self, info):
        self.cancelled = False
        print_msg(f"Connecting to server with client {self.name}", 2, info, server=self.server)
        out_log(f'Open connection to {self.ip}:{self.port}')
        out_log(f'version : {PLUGIN_METADATA["version"]}, lib version : {LIB_VERSION}')
        self.socket = soc.socket()
        try:
            self.socket.connect((self.ip, self.port))
        except Exception:
            bug_log(error=True)
            return
        self.connected = True
        self.socket.settimeout(timeout)
        self.handle_echo()

    def try_stop(self, info=None):
        if self.connected:
            self.close_connection()
            print_msg("Closed connection", 2, info, server=self.server)
        else:
            print_msg("Connection already closed", 2, info, server=self.server)

    def close_connection(self, target=''):
        if self.socket is not None and self.connected:
            self.cancelled = True
            self.send_msg(self.socket, json.dumps({'action': 'stop'}), target)
            self.socket.close()
            time.sleep(0.000001)  # for better logging priority
            out_log("Connection closed to server", debug=True)
        self.connected = False

    def reload(self, info=None):
        print_msg("Reload ChatBridgeReforged Client now", 2, info, server=self.server)
        self.close_connection()
        new_config = load_config()
        time.sleep(0.1)
        self.setup(new_config)
        print_msg("Reload Config", 2, info, server=self.server)
        self.try_start(info)
        time.sleep(0.1)
        print_msg(f"CBR status: Online = {client.connected}", 2, info, server=self.server)

    def keep_alive(self):
        while self.socket is not None and self.connected:
            out_log("keep alive", debug=True)
            for i in range(ping_time):
                time.sleep(1)
                if not self.connected:
                    return
            ping_msg = json.dumps({"action": "keepAlive", "type": "ping"})
            if self.connected:
                self.send_msg(self.socket, ping_msg)

    def login(self, name, password):
        msg = {"action": "login", "name": name, "password": password, "lib_version": LIB_VERSION, "type": CLIENT_TYPE}
        self.send_msg(self.socket, json.dumps(msg))

    def client_process(self):
        try:
            msg = self.receive_msg(self.socket, self.ip)
        except OSError as er:
            out_log("Stop Receive message", debug=True)
            self.connected = False
            raise er
        msg = json.loads(msg)
        self.process.process_msg(msg, self.socket)

    def handle_echo(self):
        self.login(self.name, self.password)
        threading.Thread(target=self.keep_alive, name='CBRPing', daemon=True).start()
        while self.socket is not None and self.connected:
            try:
                self.client_process()
            except soc.timeout:
                out_log('Connection time out!', error=True)
                out_log('Closed connection to server', debug=True)
                break
            except ConnectionAbortedError:
                out_log('Connection closed')
                bug_log()
                break
            except Exception:
                out_log("Cancel Process", debug=True)
                if not self.cancelled:
                    bug_log()
                break
            time.sleep(0.1)
        self.connected = False


def input_process(message):
    global debug_mode
    if message == 'help':
        for line in str(help_msg).splitlines():
            out_log(line)
    elif message == 'stop':
        client.try_stop()
    elif message == 'start':
        client.try_start()
    elif message == 'status':
        print_msg(f"CBR status: Online = {client.connected}", 2)
    elif message == 'ping':
        ping = client.process.ping_test()
        client.process.ping_log(ping)
    elif message == 'reload':
        client.reload()
    elif message == 'restart':
        client.try_stop()
        time.sleep(0.1)
        client.try_start()
    elif message == 'exit':
        exit(0)
    elif message == 'forcedebug':
        debug_mode = not debug_mode
        out_log(f'Force debug: {debug_mode}')
    elif message == 'test':
        for thread in threading.enumerate():
            print(thread.name)
    elif client.connected:
        client.send_msg(client.socket, client.process.msg_json_formatter(config['name'], '', message))
    else:
        out_log("Not Connected")


if __name__ == '__main__':
    config = load_config()
    client = CBRTCPClient(config)
    client.try_start()
    while True:
        input_msg = input()
        input_process(input_msg)


@new_thread("CBRProcess")
def on_info(server: ServerInterface, info: Info):
    global debug_mode
    msg = info.content
    if msg.startswith(prefix) or msg.startswith(prefix2):
        info.cancel_send_to_server()
        # if msg.endswith('<--[HERE]'):
        #    msg = msg.replace('<--[HERE]', '')
        args = msg.split(' ')
        if len(args) == 1 or args[1] == 'help':
            server.reply(info, help_msg)
        elif args[1] == 'start':
            client.try_start(info)
        elif args[1] == 'status':
            print_msg(f"CBR status: Online = {client.connected}", 2, info, server=server)
        elif args[1] == 'stop':
            client.try_stop(info)
        elif args[1] == 'reload':
            client.reload(info)
        elif args[1] == 'restart':
            client.try_stop(info)
            time.sleep(0.1)
            client.try_start(info)
            time.sleep(0.1)
            print_msg(f"CBR status: Online = {client.connected}", 2, info, server=server)
        elif args[1] == 'ping':
            ping_ms = client.process.ping_test()
            client.process.ping_log(ping_ms, info, server=server)
        elif args[1] == 'forcedebug' and server.get_permission_level(info.player) > 2:
            debug_mode = not debug_mode
            print_msg(f'Force debug: {debug_mode}', 2, info, server=server)
        elif args[1] == 'test':
            for thread in threading.enumerate():
                print(thread.name)
        else:
            print_msg("Command not Found", 2, info, server=server)
    elif info.is_player:
        if client is None:
            return
        client.try_start()
        if client.connected:
            client.send_msg(client.socket, client.process.msg_json_formatter(client.name, info.player, info.content))


def on_player_joined(server, name, info=None):
    client.try_start()
    client.send_msg(client.socket, client.process.msg_json_formatter(client.name, '', name + ' joined ' + client.name))


def on_player_left(server, name, info=None):
    client.try_start()
    client.send_msg(client.socket, client.process.msg_json_formatter(client.name, '', name + ' left ' + client.name))


def on_unload(server):
    client.close_connection()


def on_load(server, old):
    global client
    if old is not None:
        try:
            old.client.try_stop()
        except Exception:
            bug_log(error=True)
    server.register_help_message(prefix, "ChatBridgeReforged")
    config_dict = load_config()
    client = CBRTCPClient(config_dict)
    client.try_start()
    client.server = server
