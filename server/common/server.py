import socket
import logging
import signal
import threading
import time
from protocol.server_protocol import ServerProtocol
from common.utils import Bet, store_bets
from common.parser import Parser
from common.lottery_monitor import lottery_monitor


class Server:
    def __init__(self, port, listen_backlog):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        
        
        self._running = True
        self._max_threads = 10
        self._active_threads = []
        self._threads_lock = threading.Lock()

        self.lottery_monitor = lottery_monitor

        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        self._running = False
        if self._server_socket:
            self._server_socket.shutdown(socket.SHUT_RDWR)
            self._server_socket.close()
        
        self._wait_for_threads_completion()

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
        
        with self._threads_lock:
            still_alive = len([t for t in self._active_threads if t.is_alive()])
            logging.warning(f"action: shutdown_timeout | result: success | remaining_threads: {still_alive}")
            
    def handle_client_message(self,message,protocol):
        try:
            if not message:
                return False
            if message.startswith('BET|'):
                return self.handle_bet_request(message)
            if message.startswith('BATCH|'):
                return self.handle_batch_request(message)
            if message.startswith('FINISH|'):
                return self.handle_finish_request(message)
            if message.startswith('WINNERS|'):
                return self.handle_winners_request(message, protocol)
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

            success = self.lottery_monitor.add_bets([bet])
            if not success:
                return False, False

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
            
            self.lottery_monitor.add_bets(bets)
                
            cantidad = len(bets)
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {cantidad}")
            return True, False

        except Exception as e:
            logging.debug(f"action: apuesta_recibida | result: fail | cantidad: 0 | error: {e}")
            return False, False

    def handle_finish_request(self, message):
        try:
            logging.info(f"action: handle_finish_request | result: success")
            return True, False
        except Exception as e:
            logging.error(f"action: handle_finish_request | result: error | error: {e}")
            return False, False

    def handle_winners_request(self, message, protocol):
        try:
            agency_id = Parser.parse_winner(message)
            self.lottery_monitor.notify_agency_finished(agency_id)       
            winners = self.lottery_monitor.wait_for_winners(agency_id)
            err = protocol.send_message(Parser.parse_lot_winner(winners))
            if err is not None:
                logging.error(f"action: notify_winners | result: error | agency: {agency_id} | error: {err}")
            else:
                logging.info(f"action: notify_winners | result: success | agency: {agency_id} | winners_count: {len(winners)}")

            return True, True

        except Exception as e:
            logging.error(f"action: handle_winners_query | result: error | error: {e}")
            self.send_response(False, str(e))
            return False, False
    
    def run(self):
        logging.info('action: server_start | result: success')
        
        while self._running:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock:
                    client_thread = threading.Thread(
                        target=self.__handle_client_connection,
                        args=(client_sock,),
                        daemon=False
                    )
                    client_thread.start()
                    
                    with self._threads_lock:
                        self._active_threads.append(client_thread)
                        self._active_threads = [t for t in self._active_threads if t.is_alive()]

            except OSError as e:
                if self._running: 
                    logging.error(f'action: accept_connection | result: error | error: {e}')
                break

        logging.info('action: server_loop | result: success')
    
    def __handle_client_connection(self, client_sock): 
        protocol = ServerProtocol(client_sock)
        
        while self._running:        
            message = protocol.receive_message()
            
            if message:
                ok, waiting_winner = self.handle_client_message(message, protocol)
            if ok and not waiting_winner:
                protocol.send_response(True)
            elif not ok and not waiting_winner:
                protocol.send_response(False)
            elif ok and waiting_winner:
                break

    def __accept_new_connection(self):
        try:
            with self._threads_lock:
                active_count = len([t for t in self._active_threads if t.is_alive()])
                if active_count >= self._max_threads:
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