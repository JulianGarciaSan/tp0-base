package common

import (
	"fmt"
	"strconv"
	"strings"
)

type ClientParser struct{}

func NewClientParser() *ClientParser {
	return &ClientParser{}
}

func (p *ClientParser) SerializeBet(bet *Bet, agency string) []byte {
	message := fmt.Sprintf("BET|%s|%s|%s|%s|%s|%s",
		agency,
		bet.FirstName,
		bet.LastName,
		bet.Document,
		bet.Birthdate,
		bet.Number)
	return []byte(message)
}

func (p *ClientParser) SerializeBatch(bets []*Bet, agency string) []byte {
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

func (p *ClientParser) SerializeFinish(agency string) []byte {
	return []byte(fmt.Sprintf("FINISH|%s", agency))
}

func (p *ClientParser) SerializeWinnersQuery(agency string) []byte {
	return []byte(fmt.Sprintf("WINNERS|%s", agency))
}

func (p *ClientParser) ParseServerResponse(response []byte) (bool, string, error) {
	responseStr := string(response)

	if responseStr == "OK" {
		return true, "", nil
	}

	if strings.HasPrefix(responseStr, "ERROR|") {
		parts := strings.Split(responseStr, "|")
		if len(parts) >= 2 {
			return false, parts[1], nil
		}
		return false, "Unknown error", nil
	}

	return true, responseStr, nil
}

func (p *ClientParser) ParseWinnersResponse(response []byte) (int, []string, error) {
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

func (p *ClientParser) CalculateBatchMessageSize(bets []*Bet, agency string) int {
	if len(bets) == 0 {
		return 0
	}

	header := fmt.Sprintf("BATCH|%d", len(bets))
	totalSize := len(header)

	for _, bet := range bets {
		betPart := fmt.Sprintf("|%s|%s|%s|%s|%s|%s",
			agency, bet.FirstName, bet.LastName,
			bet.Document, bet.Birthdate, bet.Number)
		totalSize += len(betPart)
	}

	return totalSize
}
