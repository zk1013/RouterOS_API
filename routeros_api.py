import socket
import ssl
import hashlib
import binascii
import logging

# Constants - Define defaults
PORT = 8728
SSL_PORT = 8729

USER = 'admin'
PASSWORD = ''

USE_SSL = False
DO_LOG = False
LOG_LVL = 4  #
VERBOSE = False  # Weather to define
CONTEXT = ssl.create_default_context()  # It is possible to predefine context for SSL socket
AUTO_RELOGIN = False


class Api:

    def open_socket(self):

        try:
            # Trying to connect to RouterOS, error can occur if IP address is not reachable, or API is blocked in
            # RouterOS firewall or ip services, or port is wrong.
            self.connection = self.sock.connect((self.address, self.port))
        except OSError as e:
            exit(0)

        if self.use_ssl:
            self.sock = self.context.wrap_socket(self.sock)

    def __init__(self, address, user=USER, password=PASSWORD, use_ssl=USE_SSL, port=False, log=DO_LOG, log_lvl=LOG_LVL,
                 verbose=VERBOSE, context=CONTEXT, relogin=AUTO_RELOGIN):

        self.address = address
        self.user = user
        self.password = password
        self.use_ssl = use_ssl
        self.port = port
        self.log = log
        self.log_lvl = log_lvl
        self.verbose = verbose
        self.context = context
        self.relogin = relogin

        # Port setting logic
        if port:
            self.port = port
        elif use_ssl:
            self.port = SSL_PORT
        else:
            self.port = PORT

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection = None
        self.open_socket()

    def communicate(self, sentence):

        def read_sentence():
            rcv_sentence = []  # Words will be appended here
            rcv_length = int.from_bytes(self.sock.recv(1), byteorder='big')  # Receive the length of the next word
            trap = False  # This variable will change if there is !trap error occurred
            while rcv_length != 0:
                received = ''
                while rcv_length > len(received):
                    rec = self.sock.recv(rcv_length - len(received))
                    if rec == b'':
                        raise RuntimeError('socket connection broken')

                    # If API word from Router is too big (>127) it will send total length of
                    # the word in begining of the first part. Because of this it can't be decoded
                    # with .decode('utf-8').
                    try:
                        rec = rec.decode('utf-8')
                    except:
                        rcv_length = int.from_bytes(rec[:1], byteorder='big')
                        rec = rec[1:].decode('utf-8')
                    received += rec
                # print('<<< ', received)
                if trap:  # If !trap (error) in previous word return what was the error
                    return 'Error: RouterOS API replied: ' + received.split('=')[2]
                if received == '!trap':  # Some error occurred
                    trap = True
                rcv_sentence.append(received)
                rcv_length = int.from_bytes(self.sock.recv(1), byteorder='big')
            # print('')
            return rcv_sentence

        # Sending part of conversation

        # Each word must be sent separately.
        # First, length of the word must be sent,
        # Then, the word itself.
        for word in sentence:
            length = len(word).to_bytes(1, byteorder='big')
            self.sock.sendall(length)  # Sending the length of following word
            self.sock.sendall(word.encode('utf-8'))  # Sending the word
        self.sock.sendall(b'\x00')  # Zero length word to mark end of the sentence

        # Receiving part of the conversation

        # Will continue receiving until receives '!done' or some kind of error.
        # Everything will be appended to paragraph variable, and then returned.
        paragraph = []
        while sentence[0] != '!done':
            sentence = read_sentence()
            if 'Error' in sentence:
                return sentence
            paragraph.append(sentence)
        return paragraph

    def login(self):

        sentence = ['/login', '=name=' + self.user, '=password=' + self.password]
        reply = self.communicate(sentence)

        if len(reply[0]) == 1 and reply[0][0] == '!done':
            return reply
        elif 'Error' in reply:
            return reply
        elif len(reply[0]) == 2 and reply[0][1][0:5] == '=ret=':
            # If RouterOS uses old API login method, code continues with old method
            # print('Old API')
            md5 = hashlib.md5(('\x00' + self.password).encode('utf-8'))
            md5.update(binascii.unhexlify(reply[0][1][5:]))
            sentence = ['/login', '=name=' + self.user, '=response=00'
                        + binascii.hexlify(md5.digest()).decode('utf-8')]
            return self.communicate(sentence)

    def send(self):
        pass

    def close(self):
        pass
