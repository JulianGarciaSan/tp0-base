package common

import (
	"fmt"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/7574-sistemas-distribuidos/docker-compose-init/client/protocol"
	"github.com/op/go-logging"
)

var log = logging.MustGetLogger("log")

// ClientConfig configuración del cliente con ID, dirección del servidor y tamaño de batch
type ClientConfig struct {
	ID             string
	ServerAddress  string
	LoopAmount     int
	LoopPeriod     time.Duration
	BatchMaxAmount int
}

// Client cliente de apuestas que maneja conexión TCP y protocolo de comunicación
type Client struct {
	config   ClientConfig
	conn     net.Conn
	protocol *protocol.ClientProtocol
}

// NewClient crea un nuevo cliente
// Recibe: ClientConfig con la configuración
// Devuelve: *Client inicializado
func NewClient(config ClientConfig) *Client {
	client := &Client{
		config: config,
	}
	return client
}

// createClientSocket establece conexión TCP al servidor
// Recibe: nada (usa config interno)
// Devuelve: error si falla la conexión
func (c *Client) createClientSocket() error {
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	if err != nil {
		log.Criticalf(
			"action: connect | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
		return err
	}
	c.conn = conn
	c.protocol = protocol.NewClientProtocol(conn)
	return nil
}

// SendBet envía una apuesta individual usando variables de entorno
// Recibe: nada (lee FIRST_NAME, LAST_NAME, DOCUMENT, BIRTHDATE, NUMBER del env)
// Devuelve: error si faltan variables o falla el envío
func (c *Client) SendBet() error {
	bet := &protocol.Bet{
		FirstName: os.Getenv("FIRST_NAME"),
		LastName:  os.Getenv("LAST_NAME"),
		Document:  os.Getenv("DOCUMENT"),
		Birthdate: os.Getenv("BIRTHDATE"),
		Number:    os.Getenv("NUMBER"),
	}

	if bet.FirstName == "" || bet.LastName == "" ||
		bet.Document == "" || bet.Birthdate == "" || bet.Number == "" {
		return fmt.Errorf("faltan variables de entorno requeridas")
	}

	agency := c.config.ID

	err := c.protocol.SendBet(bet, agency)
	if err != nil {
		return err
	}

	log.Infof("action: apuesta_enviada | result: success | dni: %s | numero: %s",
		bet.Document, bet.Number)

	return nil
}

// sendBatchBet lee apuestas de CSV y las envía en lotes al servidor
// Recibe: nada (lee archivo "/data/agency-{ID}.csv")
// Devuelve: error si falla lectura de archivo o envío de lotes
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
		log.Infof("action: procesando_batch | result: in_progress | from: %d | to: %d", i, i+batchSize)

		end := i + batchSize
		if end > len(bets) {
			end = len(bets)
		}

		batch := bets[i:end]

		err := c.createClientSocket()
		if err != nil {
			return err
		}

		err = c.protocol.SendBatch(batch, c.config.ID)
		c.conn.Close()

		if err != nil {
			log.Errorf("action: enviar_batch | result: error | error: %v", err)
			return err
		}
		totalProcessed += len(batch)
		log.Infof("action: batch_enviado | result: success | cantidad: %d | total_procesado: %d", len(batch), totalProcessed)
	}

	log.Infof("action: todos_batches_enviados | result: success | total_final: %d", totalProcessed)
	return nil
}

// notifyFinished envía notificación de finalización al servidor
// Recibe: nada (usa client ID interno)
// Devuelve: error si falla la conexión o el envío
func (c *Client) notifyFinished() error {
	err := c.createClientSocket()
	if err != nil {
		return err
	}
	defer c.conn.Close()

	err = c.protocol.SendFinish(c.config.ID)
	if err != nil {
		return err
	}

	log.Infof("action: notificacion_terminado | result: success | client_id: %v", c.config.ID)
	return nil
}

// queryWinners consulta ganadores al servidor para esta agencia
// Recibe: nada (usa client ID interno)
// Devuelve: error si falla la conexión, consulta o parsing
func (c *Client) queryWinners() error {
	err := c.createClientSocket()
	if err != nil {
		return err
	}
	defer c.conn.Close()

	count, winners, err := c.protocol.QueryWinners(c.config.ID)
	if err != nil {
		return err
	}

	log.Infof("action: consulta_ganadores | result: success | cant_ganadores: %d", count)

	if count > 0 {
		log.Infof("action: ganadores_obtenidos | result: success | dnis: %v", winners)
	}

	return nil
}

// StartClientLoop ejecuta el workflow principal: envía lotes, notifica fin, consulta ganadores
// Recibe: nada (escucha SIGTERM para shutdown graceful)
// Devuelve: nada (termina al completar o recibir señal)
func (c *Client) StartClientLoop() {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM)

	select {
	case signalReceived := <-sigChan:
		if signalReceived == syscall.SIGTERM {
			return
		}
	default:
		err := c.sendBatchBet()
		if err != nil {
			log.Errorf("action: enviar_apuesta | result: error | error: %v", err)
			return
		}

		err = c.notifyFinished()
		if err != nil {
			log.Errorf("action: notificar_terminado | result: error | error: %v", err)
			return
		}

		err = c.queryWinners()

		if err != nil {
			log.Errorf("action: consulta_ganadores | result: error | error: %v", err)
			return
		}

		log.Infof("action: exit | result: success | client_id: %v", c.config.ID)
	}
}
