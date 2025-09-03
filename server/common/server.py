import socket
import logging
import signal
from protocol.server_protocol import ServerProtocol
from common.utils import Bet, store_bets
from common.parser import Parser

class Server:
    def __init__(self, port, listen_backlog):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        self._running = True
        
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self._running = False
        if self._server_socket:
            self._server_socket.shutdown(socket.SHUT_RDWR)
            self._server_socket.close()
            
    def handle_client_message(self,message):
        try:
            if not message:
                return False
            if message.startswith('BET|'):
                return self.handle_bet_request(message)
            if message.startswith('BATCH|'):
                return self.handle_batch_request(message)
            if message.startswith('FINISH|'):
                return self.handle_finish_request(message)
            else:
                return False
                
        except Exception as e:
            logging.error(f"action: handle_client_request | result: error | error: {e}")
            return False
    
    def handle_bet_request(self, message):
        try:                        
            bet = Parser.parse_bet(message)
            if not bet:
                return False, False

            store_bets([bet])

            logging.info(f"action: apuesta_almacenada | result: success | dni: {bet.document} | numero: {bet.number}")
            return True, False
            
        except Exception as e:
            logging.error(f"action: handle_bet_request | result: error | error: {e}")
            return False, False

    def handle_batch_request(self, message):
        try:
            bets, error = Parser.parse_batch(message)
            if error:
                logging.debug(f"action: apuesta_recibida | result: fail | cantidad: 0 ")
                return False, False

            store_bets(bets)
                
            cantidad = len(bets)
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {cantidad}")
            return True, False
            
        except Exception as e:
            logging.debug(f"action: apuesta_recibida | result: fail | cantidad: 0 | error: {e}")
            return False, False

    def handle_finish_request(self, message):
        try:
            logging.info(f"action: handle_finish_request | result: success")
            return True, True
        except Exception as e:
            logging.error(f"action: handle_finish_request | result: error | error: {e}")
            return False, False

    def run(self):
        while self._running:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock:
                    self.__handle_client_connection(client_sock)
            except OSError as e:
                if self._running: 
                    logging.error(f'action: accept_connection | result: error | error: {e}')
                break
        
        logging.info('action: server_loop | result: finished')
    
    def __handle_client_connection(self, client_sock): 
        while self._running:        
            protocol = ServerProtocol(client_sock)
            
            message = protocol.receive_message()
            
            if message:
                ok, finish = self.handle_client_message(message)
            if ok and not finish:
                protocol.send_response(True)
            elif not ok:
                protocol.send_response(False)
            elif finish:
                break

    def __accept_new_connection(self):
        try:
            c, addr = self._server_socket.accept()
            return c
        except socket.timeout:
            return None
        except OSError as e:
            if self._running:
                logging.error(f'action: accept_connections | result: error | error: {e}')
            return None