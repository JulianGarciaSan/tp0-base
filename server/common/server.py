import socket
import logging
import signal
from protocol.server_protocol import ServerProtocol


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
        
        addr = None
        
        addr = client_sock.getpeername()
                
        protocol = ServerProtocol(client_sock)
        
        success = protocol.handle_client_request()

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