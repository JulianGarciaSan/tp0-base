import socket
import logging
import signal
import threading
from monitor.lottery_monitor import lottery_monitor
from protocol.server_protocol import ServerProtocol

class Server:
    """
    Servidor thread-safe compatible con el main existente.
    Mantiene exactamente la misma interfaz que el Server original.
    """
    
    def __init__(self, port, listen_backlog):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        
        self._running = True
        self._max_threads = 50
        self._active_threads = 0
        self._threads_lock = threading.Lock()
        
        self._lottery_monitor = lottery_monitor
        
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        #logging.info(f"action: server_init | port: {port} | listen_backlog: {listen_backlog}")

    def _signal_handler(self, signum, frame):
        """Maneja señales de terminación"""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.shutdown(socket.SHUT_RDWR)
                self._server_socket.close()
            except:
                pass

    def run(self):
        """
        Lotería Nacional server loop
        
        Server that accepts connections from betting agencies,
        processes their bets in parallel, and stores them using 
        the thread-safe monitor.
        """
        logging.info('action: server_start | result: success')
        
        while self._running:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock:
                    client_thread = threading.Thread(
                        target=self.__handle_client_connection,
                        args=(client_sock,),
                        daemon=True  
                    )
                    client_thread.start()
                    
                    with self._threads_lock:
                        self._active_threads += 1
                        #logging.debug(f"action: thread_created | active: {self._active_threads}")

            except OSError as e:
                if self._running: 
                    logging.error(f'action: accept_connection | result: error | error: {e}')
                break
        
        logging.info('action: server_loop | result: finished')
    
    def __handle_client_connection(self, client_sock):
        """
        Handle betting agency connection
        
        Receives bet data from client, processes it using ServerProtocol,
        and stores it using the thread-safe lottery monitor.
        """
        addr = None
        thread_id = threading.current_thread().ident
        
        try:
            addr = client_sock.getpeername()
            #logging.info(f'action: client_connected | result: success | ip: {addr[0]} | thread: {thread_id}')
            
            protocol = ServerProtocol(client_sock, self._lottery_monitor)
            
            success = protocol.handle_client_request()
            
            #logging.debug(f'action: client_handled | ip: {addr[0]} | success: {success} | thread: {thread_id}')
            
        except Exception as e:
            logging.error(f"action: handle_client | result: error | ip: {addr[0] if addr else 'unknown'} | thread: {thread_id} | error: {e}")
        
        finally:
            #logging.info(f'action: close_client_connection | ip: {addr[0] if addr else "unknown"} | result: in_progress')
            try:
                client_sock.close()
                #logging.info(f'action: close_client_connection | ip: {addr[0] if addr else "unknown"} | result: success')
            except Exception as e:
                logging.error(f'action: close_client_connection | ip: {addr[0] if addr else "unknown"} | result: error | error: {e}')
            
            with self._threads_lock:
                self._active_threads -= 1
                #logging.debug(f"action: thread_finished | active: {self._active_threads}")
    
    def __accept_new_connection(self):
        """
        Accept new connections 
        
        Function blocks until a connection to a client is made.
        Then connection created is logged and returned.
        """
        try:
            with self._threads_lock:
                if self._active_threads >= self._max_threads:
                    logging.warning(f"action: max_threads_reached | limit: {self._max_threads}")
                    return None
            
            logging.debug('action: accept_connections | result: in_progress')
            c, addr = self._server_socket.accept()
            #logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
            return c
            
        except socket.timeout:
            return None
        except OSError as e:
            if self._running:
                logging.error(f'action: accept_connections | result: error | error: {e}')
            return None