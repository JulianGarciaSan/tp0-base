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

// ClientConfig Configuration used by the client
type ClientConfig struct {
	ID            string
	ServerAddress string
	LoopAmount    int
	LoopPeriod    time.Duration
}

// Client Entity that encapsulates how
type Client struct {
	config   ClientConfig
	conn     net.Conn
	protocol *protocol.ClientProtocol
}

// NewClient Initializes a new client receiving the configuration
// as a parameter
func NewClient(config ClientConfig) *Client {
	client := &Client{
		config: config,
	}
	return client
}

// CreateClientSocket Initializes client socket. In case of
// failure, error is printed in stdout/stderr and exit 1
// is returned
func (c *Client) createClientSocket() error {
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	if err != nil {
		log.Criticalf(
			"action: connect | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
	}
	c.conn = conn
	c.protocol = protocol.NewClientProtocol(conn)
	return nil
}

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

// StartClientLoop Send messages to the client until some time threshold is met
func (c *Client) StartClientLoop() {
	// There is an autoincremental msgID to identify every message sent
	// Messages if the message amount threshold has not been surpassed

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM)

	select {
	case signalReceived := <-sigChan:
		if signalReceived == syscall.SIGTERM {
			return
		}
	default:
		// Create the connection the server in every loop iteration. Send an
		// added error message in case of failure and wait the loop period
		log.Infof("Establishing connection to server %v", c.config.ServerAddress)
		err := c.createClientSocket()
		if err != nil {
			log.Errorf("action: connect | result: error | error: %v", err)
			return
		}
		defer c.conn.Close()

		log.Infof("action: connect | result: success | client_id: %v", c.config.ID)
		err = c.SendBet()
		if err != nil {
			log.Errorf("action: enviar_apuesta | result: error | error: %v", err)
			return
		}

		log.Infof("action: cliente_terminado | result: success | client_id: %v", c.config.ID)
	}
}
