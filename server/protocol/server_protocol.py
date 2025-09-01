import socket
import logging
import threading

from common.utils import Bet
from monitor.lottery_monitor import LotteryMonitor


class ServerProtocol:    
    # Constantes del protocolo
    HEADER_SIZE = 4  # Tamaño del header en bytes (uint32 BigEndian)

    # __init__ inicializa el protocolo para un cliente específico
    # Recibe: client_socket conexión TCP, monitor instancia de LotteryMonitor
    # Devuelve: nada
    def __init__(self, client_socket, monitor):
        self.client_socket = client_socket
        self.monitor = monitor
        self.thread_id = threading.current_thread().ident
        
    # _pack_uint32_be convierte entero a 4 bytes BigEndian (compatible con Go)
    # Recibe: int valor a convertir  
    # Devuelve: bytes representación BigEndian de 4 bytes
    def _pack_uint32_be(self, value):
        return value.to_bytes(self.HEADER_SIZE, byteorder='big')

    # _unpack_uint32_be convierte 4 bytes BigEndian a entero
    # Recibe: bytes data de 4 bytes en BigEndian
    # Devuelve: int valor convertido
    def _unpack_uint32_be(self, data):
        return int.from_bytes(data, byteorder='big')
        
    # receive_message recibe un mensaje completo usando protocolo length-prefixed
    # Recibe: nada (lee del socket interno)
    # Devuelve: str mensaje decodificado o None si falla
    def receive_message(self):
        try:
            header_data = self._receive_complete(self.HEADER_SIZE)
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

    # handle_client_request router principal que distribuye mensajes según tipo
    # Recibe: nada (lee mensaje del socket)
    # Devuelve: bool True si procesó correctamente, False si falló
    def handle_client_request(self):
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

    # handle_batch_request procesa lote de apuestas enviado por cliente
    # Recibe: str mensaje con formato "BATCH|cantidad|apuesta1|apuesta2|..."
    # Devuelve: bool True si procesó correctamente el batch
    def handle_batch_request(self, message):
        try:
            bets, error = self.parse_batch(message)
            if error:
                self.send_response(False, error)
                logging.debug(f"action: apuesta_recibida | result: fail | cantidad: 0 | thread: {self.thread_id}")
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
            logging.debug(f"action: apuesta_recibida | result: fail | cantidad: 0 | error: {e} | thread: {self.thread_id}")
            return False

    # handle_finished_notification procesa notificación de que agencia terminó
    # Recibe: str mensaje con formato "FINISHED|agency_id"
    # Devuelve: bool True si procesó correctamente la notificación
    def handle_finished_notification(self, message):
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

    # handle_winners_query procesa consulta de ganadores de una agencia
    # Recibe: str mensaje con formato "QUERY_WINNERS|agency_id"
    # Devuelve: bool True si envió respuesta correctamente
    def handle_winners_query(self, message):
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
        
    # send_message envía mensaje usando protocolo length-prefixed
    # Recibe: str mensaje a enviar
    # Devuelve: nada (lanza excepción si falla)
    def send_message(self, message):
        try:
            data = message.encode('utf-8')
            header = self._pack_uint32_be(len(data))
            self._send_complete(header)
            self._send_complete(data)
        except Exception as e:
            logging.error(f"action: send_message | error: {e} | thread: {self.thread_id}")
            raise
    
    # send_response envía respuesta de éxito o error al cliente
    # Recibe: bool success, str error_message opcional
    # Devuelve: nada
    def send_response(self, success, error_message=None):
        try:
            if success:
                self.send_message("OK")
            else:
                self.send_message(f"ERROR|{error_message or 'Unknown error'}")
        except Exception as e:
            logging.error(f"action: send_response | error: {e} | thread: {self.thread_id}")
    
    # _receive_complete garantiza recepción completa de bytes (evita short reads)
    # Recibe: int num_bytes cantidad de bytes a recibir
    # Devuelve: bytes datos recibidos o None si falla
    def _receive_complete(self, num_bytes):
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
    
    # _send_complete garantiza envío completo de bytes (evita short writes)
    # Recibe: bytes data datos a enviar
    # Devuelve: nada (lanza excepción si falla)
    def _send_complete(self, data):
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
    
    # parse_batch parsea mensaje tipo BATCH en lista de objetos Bet
    # Recibe: str message con formato "BATCH|cantidad|agencia|nombre|apellido|doc|fecha|numero|..."
    # Devuelve: tuple (list[Bet] apuestas, str error) donde error es None si éxito
    def parse_batch(self, message):
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