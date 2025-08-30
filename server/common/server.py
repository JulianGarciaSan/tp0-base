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
        """
        Lotería Nacional server loop
        
        Server that accepts connections from betting agencies,
        processes their bets, and stores them using the provided
        store_bets function.
        """
        # logging.info('action: server_start | result: success')
        
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
        """
        Handle betting agency connection using the betting protocol
        
        Receives bet data from client, processes it using ServerProtocol,
        and stores it using the provided store_bets function.
        """
        addr = None
        # try:
        addr = client_sock.getpeername()
        
        # logging.info(f'action: client_connected | result: success | ip: {addr[0]}')
        
        protocol = ServerProtocol(client_sock)
        
        # success = protocol.handle_bet_request()
        success = protocol.handle_batch_request()

        # except Exception as e:
        #     logging.error(f"action: handle_client | result: error | ip: {addr[0] if addr else 'unknown'} | error: {e}")
        # finally:
        #     logging.info(f'action: close_client_connection | ip: {addr[0] if addr else "unknown"} | result: in_progress')
        #     try:
        #         client_sock.close()
        #         logging.info(f'action: close_client_connection | ip: {addr[0] if addr else "unknown"} | result: success')
        #     except Exception as e:
        #         logging.error(f'action: close_client_connection | ip: {addr[0] if addr else "unknown"} | result: error | error: {e}')
    
    def __accept_new_connection(self):
        """
        Accept new connections from betting agencies
        
        Function blocks until a connection to a client is made.
        Then connection created is logged and returned.
        """
        try:
            # logging.info('action: accept_connections | result: in_progress')
            c, addr = self._server_socket.accept()
            # logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
            return c
        except socket.timeout:
            return None
        except OSError as e:
            if self._running:
                logging.error(f'action: accept_connections | result: error | error: {e}')
            return None