import threading
import logging
import os
from collections import defaultdict
from common.utils import Bet, has_won, store_bets, load_bets


class LotteryMonitor:    
    
    def __init__(self):
        self.total_agencies = int(os.environ.get('AGENCY_COUNT', 5))
        self._sorteo_realizado = False
        self._winners_cache = {}
        
        self._barrier = threading.Barrier(self.total_agencies)
        self._storage_lock = threading.Lock()

    def add_bets(self, bets):
        try:
            with self._storage_lock:
                store_bets(bets)
            
            return True
            
        except Exception as e:
            logging.error(f"action: add_bets | result: error | error: {e}")
            return False
    
    def wait_for_lottery_and_get_winners(self, agency_id):
        self._barrier.wait()
        
        with self._storage_lock:
            if not self._sorteo_realizado:
                self._execute_lottery()
        
        return self._winners_cache.get(str(agency_id), [])
    
    def _execute_lottery(self):
        if self._sorteo_realizado:
            return
        
        try:
            all_bets = list(load_bets())
        except Exception as e:
            return
        
        for bet in all_bets:
            agency_id = str(bet.agency)
            
            if agency_id not in self._winners_cache:
                self._winners_cache[agency_id] = []
            
            if has_won(bet):
                self._winners_cache[agency_id].append(bet.document)
        
        self._sorteo_realizado = True
        

    def is_sorteo_completed(self):
        with self._storage_lock: 
            return self._sorteo_realizado
        
lottery_monitor = LotteryMonitor()