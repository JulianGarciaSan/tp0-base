import logging
import os

from common.utils import has_won, load_bets

class ServerState:
    """Mantiene el estado global del servidor"""
    def __init__(self):  # Parámetro configurable
        self.agencies_finished = set()
        self.sorteo_realizado = False
        self.total_agencies = int(os.environ.get('AGENCY_COUNT', 5))
        self.winners_cache = {} 
    
    def notify_agency_finished(self, agency_id):
        """Marca una agencia como terminada y retorna si todas terminaron"""
        self.agencies_finished.add(agency_id)
        return len(self.agencies_finished) == self.total_agencies
    
    def is_sorteo_ready(self):
        return len(self.agencies_finished) == self.total_agencies
    
    def is_sorteo_done(self):
        return self.sorteo_realizado

    def perform_sorteo(self):
        """Ejecuta el sorteo y carga los ganadores"""
        if self.sorteo_realizado:
            return
            
        bets = list(load_bets())
        logging.info("action: sorteo | result: success")
        
        for bet in bets:
            agency_id = str(bet.agency)
            if agency_id not in self.winners_cache:
                self.winners_cache[agency_id] = []
            
            if has_won(bet):
                self.winners_cache[agency_id].append(bet.document)
        
        self.sorteo_realizado = True

server_state = ServerState()