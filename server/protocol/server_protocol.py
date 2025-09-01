import socket
import logging
import threading

from common.utils import Bet
from monitor.lottery_monitor import LotteryMonitor


class ServerProtocol:
    """Protocolo del servidor thread-safe - SIN usar struct"""
    
    def __init__(self, client_socket, monitor):
        self.client_socket = client_socket
        self.monitor = monitor
        self.thread_id = threading.current_thread().ident
        
    def _pack_uint32_be(self, value):
        """Convierte uint32 a 4 bytes BigEndian (reemplaza struct.pack('!I', value))"""
        return value.to_bytes(4, byteorder='big')
    
    def _unpack_uint32_be(self, data):
        """Convierte 4 bytes BigEndian a uint32 (reemplaza struct.unpack('!I', data)[0])"""
        return int.from_bytes(data, byteorder='big')
        
    def receive_message(self):
        """Recibe un mensaje completo leyendo primero la longitud"""
        try:
            header_data = self._receive_complete(4)
            if not header_data:
                return None
            
            message_length = self._unpack_uint32_be(header_data)
            message_data = self._receive_complete(message_length)
            if not message_data:
                return None
                
            return message_data.decode('utf-8')
        except Exception as e:
            logging.error(f"action: receive_message | error: {e} | thread: {self.thread_id}")
            return None

    def handle_client_request(self):
        """Punto de entrada principal - router de mensajes thread-safe"""
        try:
            message = self.receive_message()
            if not message:
                return False
            
            if message.startswith('BATCH|'):
                return self.handle_batch_request(message)
            elif message.startswith('FINISHED|'):
                return self.handle_finished_notification(message)
            elif message.startswith('QUERY_WINNERS|'):
                return self.handle_winners_query(message)
            else:
                self.send_response(False, "Unknown message type")
                return False
                
        except Exception as e:
            logging.error(f"action: handle_client_request | result: error | error: {e} | thread: {self.thread_id}")
            return False

    def handle_batch_request(self, message):
        """Maneja un batch de apuestas usando el monitor"""
        try:
            bets, error = self.parse_batch(message)
            if error:
                self.send_response(False, error)
                logging.info(f"action: apuesta_recibida | result: fail | cantidad: 0 | thread: {self.thread_id}")
                return False
            
            success = self.monitor.add_bets(bets)
            if not success:
                self.send_response(False, "Error storing bets")
                return False
                
            cantidad = len(bets)
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {cantidad} | thread: {self.thread_id}")
            self.send_response(True)
            return True
            
        except Exception as e:
            self.send_response(False, str(e))
            logging.info(f"action: apuesta_recibida | result: fail | cantidad: 0 | error: {e} | thread: {self.thread_id}")
            return False

    def handle_finished_notification(self, message):
        """Maneja notificación usando el monitor"""
        try:
            parts = message.split('|')
            if len(parts) != 2:
                self.send_response(False, "Invalid FINISHED format")
                return False
            
            agency_id = parts[1]
            all_ready = self.monitor.notify_agency_finished(agency_id)
            
            self.send_response(True)
            return True
            
        except Exception as e:
            logging.error(f"action: handle_finished_notification | result: error | error: {e} | thread: {self.thread_id}")
            self.send_response(False, str(e))
            return False

    def handle_winners_query(self, message):
        """Maneja consulta de ganadores usando el monitor"""
        try:
            parts = message.split('|')
            if len(parts) != 2:
                self.send_response(False, "Invalid QUERY_WINNERS format")
                return False
            
            agency_id = parts[1]
            winners = self.monitor.wait_for_winners(agency_id)
            
            # Enviar respuesta
            winners_str = ','.join(winners) if winners else ""
            self.send_message(f"WINNERS|{len(winners)}|{winners_str}")
            
            return True
            
        except Exception as e:
            logging.error(f"action: handle_winners_query | result: error | error: {e} | thread: {self.thread_id}")
            self.send_response(False, str(e))
            return False
        
    def send_message(self, message):
        """Envía un mensaje con longitud al principio"""
        try:
            data = message.encode('utf-8')
            # CAMBIO: reemplaza struct.pack('!I', len(data))
            header = self._pack_uint32_be(len(data))
            self._send_complete(header)
            self._send_complete(data)
        except Exception as e:
            logging.error(f"action: send_message | error: {e} | thread: {self.thread_id}")
            raise
    
    def send_response(self, success, error_message=None):
        """Envía respuesta al cliente"""
        try:
            if success:
                self.send_message("OK")
            else:
                self.send_message(f"ERROR|{error_message or 'Unknown error'}")
        except Exception as e:
            logging.error(f"action: send_response | error: {e} | thread: {self.thread_id}")
    
    def _receive_complete(self, num_bytes):
        """Recepción completa para evitar short-read"""
        buffer = b''
        try:
            while len(buffer) < num_bytes:
                chunk = self.client_socket.recv(num_bytes - len(buffer))
                if not chunk:
                    return None 
                buffer += chunk
            return buffer
        except Exception as e:
            logging.error(f"action: receive_complete | error: {e} | thread: {self.thread_id}")
            return None
    
    def _send_complete(self, data):
        """Envío completo para evitar short-write"""
        total_sent = 0
        try:
            while total_sent < len(data):
                sent = self.client_socket.send(data[total_sent:])
                if sent == 0:
                    raise RuntimeError("Socket connection broken")
                total_sent += sent
        except Exception as e:
            logging.error(f"action: send_complete | error: {e} | thread: {self.thread_id}")
            raise
    
    def parse_batch(self, message):
        """Parsea mensaje con formato: BATCH|cantidad|apuesta1|apuesta2|..."""
        try:
            parts = message.split('|')
            if parts[0] != 'BATCH':
                return None, "Invalid batch format"
            
            cantidad = int(parts[1])
            expected_fields = 2 + (cantidad * 6)
            
            if len(parts) != expected_fields:
                return None, f"Expected {expected_fields} fields, got {len(parts)}"
            
            bets = []
            for i in range(cantidad):
                base_idx = 2 + (i * 6)
                agency = parts[base_idx]
                first_name = parts[base_idx + 1]
                last_name = parts[base_idx + 2]
                document = parts[base_idx + 3]
                birthdate = parts[base_idx + 4]
                number = parts[base_idx + 5]
                
                bet = Bet(agency, first_name, last_name, document, birthdate, number)
                bets.append(bet)
            
            return bets, None
        
        except Exception as e:
            logging.error(f"action: parse_batch | error: {e} | thread: {self.thread_id}")
            return None, str(e)