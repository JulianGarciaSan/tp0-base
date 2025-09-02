package protocol

import (
	"encoding/binary"
	"fmt"
	"net"
)

type Bet struct {
	FirstName string
	LastName  string
	Document  string
	Birthdate string
	Number    string
}

type ClientProtocol struct {
	conn net.Conn
}

func NewClientProtocol(conn net.Conn) *ClientProtocol {
	return &ClientProtocol{
		conn: conn,
	}
}

func (cp *ClientProtocol) SerializeBet(bet *Bet, agency string) []byte {
	message := fmt.Sprintf("BET|%s|%s|%s|%s|%s|%s",
		agency,
		bet.FirstName,
		bet.LastName,
		bet.Document,
		bet.Birthdate,
		bet.Number)
	return []byte(message)
}

func (cp *ClientProtocol) SerializeBatch(bets []*Bet, agency string) []byte {
	message := fmt.Sprintf("BATCH|%d", len(bets))

	for _, bet := range bets {
		betStr := fmt.Sprintf("|%s|%s|%s|%s|%s|%s",
			agency,
			bet.FirstName,
			bet.LastName,
			bet.Document,
			bet.Birthdate,
			bet.Number)
		message += betStr
	}

	return []byte(message)
}

func (cp *ClientProtocol) SendMessage(data []byte) error {
	header := make([]byte, 4)
	binary.BigEndian.PutUint32(header, uint32(len(data)))

	if err := cp.sendComplete(header); err != nil {
		return fmt.Errorf("error enviando header: %v", err)
	}

	if err := cp.sendComplete(data); err != nil {
		return fmt.Errorf("error enviando mensaje: %v", err)
	}

	return nil
}

func (cp *ClientProtocol) ReceiveMessage() ([]byte, error) {
	header := make([]byte, 4)
	if err := cp.receiveComplete(header); err != nil {
		return nil, fmt.Errorf("error leyendo header: %v", err)
	}
	messageLength := binary.BigEndian.Uint32(header)

	message := make([]byte, messageLength)
	if err := cp.receiveComplete(message); err != nil {
		return nil, fmt.Errorf("error leyendo mensaje: %v", err)
	}

	return message, nil
}

func (cp *ClientProtocol) sendComplete(data []byte) error {
	totalSent := 0
	for totalSent < len(data) {
		n, err := cp.conn.Write(data[totalSent:])
		if err != nil {
			return err
		}
		totalSent += n
	}
	return nil
}

func (cp *ClientProtocol) receiveComplete(data []byte) error {
	totalReceived := 0
	for totalReceived < len(data) {
		n, err := cp.conn.Read(data[totalReceived:])
		if err != nil {
			return err
		}
		totalReceived += n
	}
	return nil
}

func (cp *ClientProtocol) SendBet(bet *Bet, agency string) error {
	data := cp.SerializeBet(bet, agency)

	if err := cp.SendMessage(data); err != nil {
		return err
	}

	response, err := cp.ReceiveMessage()
	if err != nil {
		return err
	}

	if string(response) != "OK" {
		return fmt.Errorf("servidor rechazó apuesta: %s", string(response))
	}

	return nil
}

func (cp *ClientProtocol) SendBatch(bets []*Bet, agency string) error {
	data := cp.SerializeBatch(bets, agency)

	if err := cp.SendMessage(data); err != nil {
		return err
	}

	response, err := cp.ReceiveMessage()
	if err != nil {
		return err
	}

	if string(response) != "OK" {
		return fmt.Errorf("servidor rechazó batch: %s", string(response))
	}

	return nil
}
