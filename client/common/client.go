package common

import (
	"fmt"
	"net"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/7574-sistemas-distribuidos/docker-compose-init/client/protocol"
	"github.com/op/go-logging"
)

var log = logging.MustGetLogger("log")

type ClientConfig struct {
	ID             string
	ServerAddress  string
	LoopAmount     int
	LoopPeriod     time.Duration
	BatchMaxAmount int
}

type Client struct {
	config   ClientConfig
	conn     net.Conn
	protocol *protocol.ClientProtocol
	shutdown bool
}

func NewClient(config ClientConfig) *Client {
	return &Client{config: config}
}

func (c *Client) createClientSocket() error {
	conn, err := net.DialTimeout("tcp", c.config.ServerAddress, 5*time.Second)
	if err != nil {
		log.Criticalf("action: connect | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return err
	}
	c.conn = conn
	c.protocol = protocol.NewClientProtocol(conn)
	return nil
}

func (c *Client) isServerGone(err error) bool {
	if err == nil {
		return false
	}
	errStr := err.Error()
	return strings.Contains(errStr, "broken pipe") ||
		strings.Contains(errStr, "connection reset") ||
		strings.Contains(errStr, "EOF")
}

func (c *Client) sendBatchBet() error {
	filePath := fmt.Sprintf("/data/agency-%s.csv", c.config.ID)
	bets, err := c.protocol.ReadBetsFromFile(filePath, c.config.ID)
	if err != nil {
		return err
	}

	log.Infof("action: archivo_leido | result: success | total_apuestas: %d", len(bets))

	batchSize := c.config.BatchMaxAmount
	totalProcessed := 0

	for i := 0; i < len(bets); i += batchSize {
		if c.shutdown {
			log.Infof("action: shutdown_detected | processed: %d | stopping_gracefully", totalProcessed)
			return nil
		}

		log.Infof("action: procesando_batch | result: in_progress | from: %d | to: %d", i, i+batchSize)

		end := i + batchSize
		if end > len(bets) {
			end = len(bets)
		}

		batch := bets[i:end]
		err = c.protocol.SendBatch(batch, c.config.ID)

		if err != nil {
			if c.isServerGone(err) {
				log.Infof("action: server_disconnected | processed: %d | stopping_gracefully", totalProcessed)
				return nil
			}
			log.Errorf("action: enviar_batch | result: error | error: %v", err)
			return err
		}

		totalProcessed += len(batch)
		log.Infof("action: batch_enviado | result: success | cantidad: %d | total_procesado: %d",
			len(batch), totalProcessed)
	}

	log.Infof("action: todos_batches_enviados | result: success | total_final: %d", totalProcessed)
	return nil
}

func (c *Client) SendFinish() error {
	if c.shutdown {
		return nil
	}

	err := c.protocol.SendFinish(c.config.ID)
	if err != nil {
		if c.isServerGone(err) {
			log.Infof("action: server_gone_during_finish | client_id: %v", c.config.ID)
			return nil
		}
		return err
	}

	log.Infof("action: enviar_finalizar | result: success | client_id: %v", c.config.ID)
	return nil
}

func (c *Client) Winners() error {
	if c.shutdown {
		return nil
	}

	count, winners, err := c.protocol.Winners(c.config.ID)
	if err != nil {
		if c.isServerGone(err) {
			log.Infof("action: server_gone_during_winners | client_id: %v", c.config.ID)
			return nil
		}
		return err
	}

	log.Infof("action: consulta_ganadores | result: success | cant_ganadores: %d", count)
	if count > 0 {
		log.Infof("action: ganadores_obtenidos | result: success | dnis: %v", winners)
	}
	return nil
}

func (c *Client) StartClientLoop() {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)

	go func() {
		<-sigChan
		log.Infof("action: shutdown_signal | client_id: %v", c.config.ID)
		c.shutdown = true
	}()

	defer func() {
		if c.conn != nil {
			c.conn.Close()
		}
	}()

	err := c.createClientSocket()
	if err != nil {
		return
	}

	if err := c.sendBatchBet(); err != nil {
		log.Errorf("action: batch_error | error: %v", err)
		return
	}

	if err := c.SendFinish(); err != nil {
		log.Errorf("action: finish_error | error: %v", err)
		return
	}

	if err := c.Winners(); err != nil {
		log.Errorf("action: winners_error | error: %v", err)
		return
	}

	log.Infof("action: exit | result: success | client_id: %v", c.config.ID)
}
