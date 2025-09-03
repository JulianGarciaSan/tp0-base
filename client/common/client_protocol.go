package common

import (
	"encoding/binary"
	"fmt"
	"net"
)

type ClientProtocol struct {
	conn   net.Conn
	parser *ClientParser
}

func NewClientProtocol(conn net.Conn) *ClientProtocol {
	return &ClientProtocol{
		conn:   conn,
		parser: NewClientParser(),
	}
}

const (
	HeaderSize = 4 // Tamaño del header en bytes
)

func (cp *ClientProtocol) SendMessage(data []byte) error {
	header := make([]byte, HeaderSize)
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
	header := make([]byte, HeaderSize)
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
	data := cp.parser.SerializeBet(bet, agency)

	if err := cp.SendMessage(data); err != nil {
		return err
	}

	response, err := cp.ReceiveMessage()
	if err != nil {
		return err
	}

	success, errorMsg, err := cp.parser.ParseServerResponse(response)
	if err != nil {
		return err
	}

	if !success {
		return fmt.Errorf("servidor rechazó apuesta: %s", errorMsg)
	}

	return nil
}

func (cp *ClientProtocol) SendBatch(bets []*Bet, agency string) error {
	data := cp.parser.SerializeBatch(bets, agency)

	if err := cp.SendMessage(data); err != nil {
		return err
	}

	response, err := cp.ReceiveMessage()
	if err != nil {
		return err
	}

	success, errorMsg, err := cp.parser.ParseServerResponse(response)
	if err != nil {
		return err
	}

	if !success {
		return fmt.Errorf("servidor rechazó batch: %s", errorMsg)
	}

	return nil
}

func (cp *ClientProtocol) SendFinish(agency string) error {
	data := cp.parser.SerializeFinish(agency)

	if err := cp.SendMessage(data); err != nil {
		return err
	}

	response, err := cp.ReceiveMessage()
	if err != nil {
		return err
	}

	success, errorMsg, err := cp.parser.ParseServerResponse(response)
	if err != nil {
		return err
	}

	if !success {
		return fmt.Errorf("servidor rechazó finalizar: %s", errorMsg)
	}

	return nil
}

func (cp *ClientProtocol) Winners(agency string) (int, []string, error) {
	data := cp.parser.SerializeWinnersQuery(agency)

	if err := cp.SendMessage(data); err != nil {
		return 0, nil, err
	}

	response, err := cp.ReceiveMessage()
	if err != nil {
		return 0, nil, err
	}

	return cp.parser.ParseWinnersResponse(response)
}
