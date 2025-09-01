import socket
import logging
import signal
import threading
import time
from monitor.lottery_monitor import lottery_monitor
from protocol.server_protocol import ServerProtocol

class Server:    
    # __init__ inicializa servidor con socket y configuración de threads
    # Recibe: int port puerto de escucha, int listen_backlog tamaño de cola de conexiones
    # Devuelve: nada
    def __init__(self, port, listen_backlog):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        
        self._running = True
        self._max_threads = 50
        self._active_threads = []
        self._threads_lock = threading.Lock()
        
        self._lottery_monitor = lottery_monitor
        
        signal.signal(signal.SIGTERM, self._signal_handler)

        #logging.debug(f"action: server_init | port: {port} | listen_backlog: {listen_backlog}")

    # _signal_handler maneja señal SIGTERM para graceful shutdown
    # Recibe: int signum número de señal, frame frame actual
    # Devuelve: nada
    def _signal_handler(self, signum, frame):
        #logging.debug("action: shutdown_signal_received | initiating_graceful_shutdown: true")
        self._running = False
        
        # Cerrar socket del servidor para no aceptar más conexiones
        if self._server_socket:
            try:
                self._server_socket.shutdown(socket.SHUT_RDWR)
                self._server_socket.close()
            except:
                pass
        
        # Esperar que terminen los threads activos
        self._wait_for_threads_completion()

    # _wait_for_threads_completion espera que todos los threads activos terminen
    # Recibe: nada
    # Devuelve: nada
    def _wait_for_threads_completion(self):
        max_wait_time = 30
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            with self._threads_lock:
                active_count = len([t for t in self._active_threads if t.is_alive()])
                if active_count == 0:
                    logging.debug("action: all_threads_completed | result: success")
                    return

                logging.debug(f"action: waiting_threads_completion | result: success | active_threads: {active_count}")

            time.sleep(1)
        
        # Si llegamos aquí, algunos threads no terminaron a tiempo
        with self._threads_lock:
            still_alive = len([t for t in self._active_threads if t.is_alive()])
            logging.warning(f"action: shutdown_timeout | result: success | remaining_threads: {still_alive}")

    # run ejecuta el loop principal del servidor que acepta conexiones
    # Recibe: nada
    # Devuelve: nada
    def run(self):
        logging.info('action: server_start | result: success')
        
        while self._running:
            try:
                client_sock = self._accept_new_connection()
                if client_sock:
                    client_thread = threading.Thread(
                        target=self._handle_client_connection,
                        args=(client_sock,),
                        daemon=False  # No daemon para graceful shutdown
                    )
                    client_thread.start()
                    
                    with self._threads_lock:
                        self._active_threads.append(client_thread)
                        # Limpiar threads terminados
                        self._active_threads = [t for t in self._active_threads if t.is_alive()]

            except OSError as e:
                if self._running: 
                    logging.error(f'action: accept_connection | result: error | error: {e}')
                break

        logging.info('action: server_loop | result: success')

    # _handle_client_connection procesa conexión de cliente usando ServerProtocol
    # Recibe: socket client_sock conexión del cliente
    # Devuelve: nada
    def _handle_client_connection(self, client_sock):
        addr = None
        thread_id = threading.current_thread().ident
        
        try:
            addr = client_sock.getpeername()
            logging.debug(f'action: client_connected | result: success | ip: {addr[0]} | thread: {thread_id}')
            
            protocol = ServerProtocol(client_sock, self._lottery_monitor)
            
            success = protocol.handle_client_request()
            
            if not success:
                logging.warning(f'action: client_handled | result: error | ip: {addr[0]} | success: false | thread: {thread_id}')
            
        except Exception as e:
            logging.error(f"action: handle_client | result: error | ip: {addr[0] if addr else 'unknown'} | thread: {thread_id} | error: {e}")
        
        finally:
            try:
                client_sock.close()
                logging.info(f'action: close_client_connection | result: success | ip: {addr[0] if addr else "unknown"} ')
            except Exception as e:
                logging.error(f'action: close_client_connection | result: error | ip: {addr[0] if addr else "unknown"} | error: {e}')
    
    # _accept_new_connection acepta nueva conexión si no se alcanzó límite de threads
    # Recibe: nada
    # Devuelve: socket conexión de cliente o None si no puede aceptar
    def _accept_new_connection(self):
        try:
            with self._threads_lock:
                active_count = len([t for t in self._active_threads if t.is_alive()])
                if active_count >= self._max_threads:
                    #logging.warning(f"action: max_threads_reached | limit: {self._max_threads}")
                    return None
            
            c, addr = self._server_socket.accept()
            logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
            return c
            
        except socket.timeout:
            return None
        except OSError as e:
            if self._running:
                logging.error(f'action: accept_connections | result: error | error: {e}')
            return None