import threading
import logging
import os
from collections import defaultdict
from common.utils import Bet, has_won, store_bets, load_bets


class LotteryMonitor:
    """
    Monitor que encapsula toda la lógica de manejo de apuestas y sorteo.
    Garantiza thread-safety usando las funciones de common.utils.
    """
    
    def __init__(self):
        self.total_agencies = int(os.environ.get('AGENCY_COUNT', 5))
        
        self._agencies_finished = set() 
        self._sorteo_realizado = False
        self._winners_cache = {}
        
        self._monitor_lock = threading.RLock()
        self._sorteo_condition = threading.Condition(self._monitor_lock)
        self._storage_lock = threading.Lock() 

        #logging.info(f"action: lottery_monitor_init | total_agencies: {self.total_agencies}")

    def add_bets(self, bets):
        """
        Añade un batch de apuestas usando store_bets() de forma thread-safe.
        Retorna True si se añadieron correctamente.
        """
        try:
            with self._storage_lock:
                store_bets(bets)
            
            #logging.info(f"action: bets_stored | batch_size: {len(bets)}")
            return True
            
        except Exception as e:
            logging.error(f"action: add_bets | result: error | error: {e}")
            return False
    
    def notify_agency_finished(self, agency_id):
        """
        Notifica que una agencia terminó de enviar apuestas.
        Si todas las agencias terminaron, ejecuta el sorteo automáticamente.
        Retorna True si todas las agencias han terminado.
        """
        with self._sorteo_condition:
            self._agencies_finished.add(agency_id)
            finished_count = len(self._agencies_finished)
            
            #logging.info(f"action: agency_finished | agency: {agency_id} | finished: {finished_count}/{self.total_agencies}")
            
            all_finished = finished_count == self.total_agencies
            
            if all_finished and not self._sorteo_realizado:
                #logging.info("action: all_agencies_finished | executing_sorteo: true")
                self._execute_sorteo()
                self._sorteo_condition.notify_all()
            
            return all_finished
    
    def wait_for_winners(self, agency_id):
        """
        Espera a que el sorteo termine y retorna los ganadores de la agencia.
        Este método bloquea hasta que el sorteo esté completo.
        """
        with self._sorteo_condition:
            while not self._sorteo_realizado:
                #logging.info(f"action: waiting_for_sorteo | agency: {agency_id}")
                self._sorteo_condition.wait()
            
            winners = self._winners_cache.get(agency_id, [])
            #logging.info(f"action: winners_retrieved | agency: {agency_id} | count: {len(winners)}")
            return winners
    
    def _execute_sorteo(self):
        """
        Ejecuta el sorteo usando load_bets(). DEBE ser llamado con el monitor lock tomado.
        Procesa todas las apuestas y determina ganadores por agencia.
        """
        if self._sorteo_realizado:
            #logging.warning("action: sorteo_already_executed | skipping: true")
            return
        
        #logging.info("action: sorteo_start | loading_bets: true")
        
        try:
            all_bets = list(load_bets())
            total_bets = len(all_bets)
            logging.info(f"action: bets_loaded | total_bets: {total_bets}")
        except Exception as e:
            logging.error(f"action: load_bets | result: error | error: {e}")
            return
        
        for bet in all_bets:
            agency_id = str(bet.agency)
            
            if agency_id not in self._winners_cache:
                self._winners_cache[agency_id] = []
            
            if has_won(bet):
                self._winners_cache[agency_id].append(bet.document)
        
        self._sorteo_realizado = True
        
        total_winners = sum(len(winners) for winners in self._winners_cache.values())
        agencies_with_winners = len([a for a, w in self._winners_cache.items() if len(w) > 0])
        
        logging.info(f"action: sorteo_completed | total_bets: {total_bets} | total_winners: {total_winners} | agencies_with_winners: {agencies_with_winners}")

    def is_sorteo_completed(self):
        """Retorna True si el sorteo ya fue ejecutado."""
        with self._monitor_lock:
            return self._sorteo_realizado
    
    def get_agencies_status(self):
        """Retorna el estado de las agencias."""
        with self._monitor_lock:
            return {
                'finished_agencies': list(self._agencies_finished),
                'pending_agencies': self.total_agencies - len(self._agencies_finished),
                'all_finished': len(self._agencies_finished) == self.total_agencies
            }


# Instancia global del monitor
lottery_monitor = LotteryMonitor()