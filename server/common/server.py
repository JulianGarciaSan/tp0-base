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
        self._active_connections = [] 
        self._threads_lock = threading.Lock()

        self.lottery_monitor = lottery_monitor

        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        logging.info(f"action: received_signal | signal: {signum} | result: starting_shutdown")

        self._running = False
                
        self._interrupt_lottery_barrier()
        
        time.sleep(0.1)
        
        self._close_active_connections()
        
        try:
            if self._server_socket:
                self._server_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass  
        finally:
            if self._server_socket:
                self._server_socket.close()
        
        self._wait_for_threads_completion()
        
        logging.info("action: graceful_shutdown | result: completed")

    def _close_active_connections(self):
        with self._threads_lock:
            for conn in self._active_connections[:]:  
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                    conn.close()
                except OSError:
                    pass        
        logging.info(f"action: close_connections | closed_count: {len(self._active_connections)}")

    def _interrupt_lottery_barrier(self):
        try:                        
            if hasattr(self.lottery_monitor, '_barrier'):
                try:
                    self.lottery_monitor._barrier.abort()
                except threading.BrokenBarrierError:
                    pass
        except Exception as e:
            logging.debug(f"action: interrupt_barrier | error: {e}")
            
            
    def _wait_for_threads_completion(self):
        max_wait_time = 30
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            with self._threads_lock:
                active_threads = [t for t in self._active_threads if t.is_alive()]
                if not active_threads:
                    logging.info("action: all_threads_completed | result: success")
                    return
                
                logging.debug(f"action: waiting_threads_completion | active_threads: {len(active_threads)}")
            
            time.sleep(0.5)
        
        with self._threads_lock:
            still_alive = [t for t in self._active_threads if t.is_alive()]
            logging.warning(f"action: shutdown_timeout | remaining_threads: {len(still_alive)}")
            
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
            winners = self.lottery_monitor.wait_for_lottery_and_get_winners(agency_id)
            
            success = protocol.send_message(Parser.parse_lot_winner(winners))
            if not success:
                logging.error(f"action: notify_winners | result: error | agency: {agency_id} | error: client_gone")
            else:
                logging.info(f"action: notify_winners | result: success | agency: {agency_id} | winners_count: {len(winners)}")

            return True, True
        
        except threading.BrokenBarrierError:
            logging.debug(f"action: lottery_interrupted_by_shutdown | agency: {agency_id}")
            return False, False
        except Exception as e:
            logging.error(f"action: handle_winners_request | result: error | error: {e}")
            return False, False
    
    def run(self):
        logging.info('action: server_start | result: success')
        
        while self._running:
            try:
                client_sock = self.__accept_new_connection()
                if client_sock:
                    
                    with self._threads_lock:
                        self._active_connections.append(client_sock)
                        
                    client_thread = threading.Thread(
                        target=self.__handle_client_connection,
                        args=(client_sock,),
                        daemon=False
                    )
                    
                    client_thread.start()
                    
                    with self._threads_lock:
                        self._active_threads.append(client_thread)
                        self._active_threads = [t for t in self._active_threads if t.is_alive()]
            except socket.timeout:
                continue
            except OSError as e:
                if self._running: 
                    logging.error(f'action: accept_connection | result: error | error: {e}')
                break

        logging.info('action: server_loop | result: success')
    
    def __handle_client_connection(self, client_sock): 
        try:
            protocol = ServerProtocol(client_sock)
            
            while self._running:        
                message = protocol.receive_message()
                
                if message:
                    ok, waiting_winner = self.handle_client_message(message, protocol)
                if ok and not waiting_winner:
                    success = protocol.send_response(True)
                    if not success:
                        break
                elif not ok and not waiting_winner:
                    success = protocol.send_response(False)
                    if not success:
                        break
                elif ok and waiting_winner:
                    break
        finally:
            try:
                client_sock.close()
            except:
                pass
            
        with self._threads_lock:
            if client_sock in self._active_connections:
                self._active_connections.remove(client_sock)
                
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