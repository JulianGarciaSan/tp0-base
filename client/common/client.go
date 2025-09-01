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

func (c *Client) StartClientLoop() {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM)

	select {
	case signalReceived := <-sigChan:
		if signalReceived == syscall.SIGTERM {
			return
		}
	default:
		err := c.createClientSocket()
		if err != nil {
			log.Errorf("action: connect | result: error | error: %v", err)
			return
		}
		defer c.conn.Close()

		err = c.SendBet()
		if err != nil {
			return
		}
	}
}
