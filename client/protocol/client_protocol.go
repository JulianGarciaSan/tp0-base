package protocol

import (
	"encoding/binary"
	"fmt"
	"log"
	"net"
	"strconv"
	"strings"
)

// Bet estructura de una apuesta con datos del apostador
type Bet struct {
	FirstName string
	LastName  string
	Document  string
	Birthdate string
	Number    string
}

// ClientProtocol maneja la comunicación con el servidor usando TCP
type ClientProtocol struct {
	conn net.Conn
}

// NewClientProtocol crea un nuevo protocolo cliente
// Recibe: net.Conn conexión TCP establecida
// Devuelve: *ClientProtocol inicializado
func NewClientProtocol(conn net.Conn) *ClientProtocol {
	return &ClientProtocol{
		conn: conn,
	}
}

// SerializeBet convierte una apuesta a formato de mensaje del protocolo
// Recibe: *Bet apuesta, string agencia
// Devuelve: []byte mensaje serializado formato "APUESTA|agencia|nombre|apellido|doc|fecha|numero"
func (cp *ClientProtocol) SerializeBet(bet *Bet, agency string) []byte {
	message := fmt.Sprintf("APUESTA|%s|%s|%s|%s|%s|%s",
		agency,
		bet.FirstName,
		bet.LastName,
		bet.Document,
		bet.Birthdate,
		bet.Number)
	return []byte(message)
}

// SerializeBatch convierte múltiples apuestas a formato batch del protocolo
// Recibe: []*Bet slice de apuestas, string agencia (id)
// Devuelve: []byte mensaje serializado formato "BATCH|cantidad|apuesta1|apuesta2|..."
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

// SendMessage envía datos usando protocolo length-prefixed (4 bytes header + payload)
// Recibe: []byte datos a enviar
// Devuelve: error si falla el envío
func (cp *ClientProtocol) SendMessage(data []byte) error {
	header := make([]byte, 4)
	binary.BigEndian.PutUint32(header, uint32(len(data)))

	if err := cp.sendComplete(header); err != nil {
		return fmt.Errorf("error enviando header: %v", err)
	}

	if err := cp.sendComplete(data); err != nil {
		return fmt.Errorf("error enviando mensaje: %v", err)
	}
	log.Printf("action: send_message | result: success | bytes_sent: %d", len(data)+4)
	return nil
}

// ReceiveMessage recibe datos usando protocolo length-prefixed
// Recibe: nada
// Devuelve: []byte datos recibidos, error si falla la recepción
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

// sendComplete garantiza que todos los bytes se envíen completamente
// Recibe: []byte datos a enviar
// Devuelve: error si falla el envío
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

// receiveComplete garantiza que todos los bytes se reciban completamente
// Recibe: []byte buffer donde recibir datos
// Devuelve: error si falla la recepción
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

// SendBet envía una apuesta individual y espera confirmación del servidor
// Recibe: *Bet apuesta, string agencia
// Devuelve: error si falla envío o servidor rechaza
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

// SendBatch envía múltiples apuestas en un lote y espera confirmación
// Recibe: []*Bet slice de apuestas, string agencia
// Devuelve: error si falla envío o servidor rechaza
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

// SendFinish notifica al servidor que la agencia terminó de enviar apuestas
// Recibe: string agencia
// Devuelve: error si falla envío o servidor rechaza
func (cp *ClientProtocol) SendFinish(agency string) error {
	data := []byte(fmt.Sprintf("FINISHED|%s", agency))
	if err := cp.SendMessage(data); err != nil {
		return err
	}

	response, err := cp.ReceiveMessage()
	if err != nil {
		return err
	}

	if string(response) != "OK" {
		return fmt.Errorf("servidor rechazó finish: %s", string(response))
	}

	return nil
}

// QueryWinners consulta ganadores de la lotería para una agencia
// Recibe: string agencia
// Devuelve: int cantidad de ganadores, []string lista de DNIs ganadores, error si falla
func (cp *ClientProtocol) QueryWinners(agency string) (int, []string, error) {
	data := []byte(fmt.Sprintf("QUERY_WINNERS|%s", agency))
	if err := cp.SendMessage(data); err != nil {
		return 0, nil, err
	}

	response, err := cp.ReceiveMessage()
	if err != nil {
		return 0, nil, err
	}

	responseStr := string(response)

	parts := strings.Split(responseStr, "|")
	if len(parts) != 3 || parts[0] != "WINNERS" {
		return 0, nil, fmt.Errorf("respuesta inválida: %s", responseStr)
	}

	count, err := strconv.Atoi(parts[1])
	if err != nil {
		return 0, nil, fmt.Errorf("count inválido: %v", err)
	}

	var winners []string
	if count > 0 && parts[2] != "" {
		winners = strings.Split(parts[2], ",")
	}

	return count, winners, nil
}
