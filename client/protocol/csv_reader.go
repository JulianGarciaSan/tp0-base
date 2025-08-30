package protocol

import (
	"encoding/csv"
	"fmt"
	"os"
)

func (cp *ClientProtocol) ReadBetsFromFile(filePath string, agency string) ([]*Bet, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("error opening file: %v", err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("error reading CSV: %v", err)
	}

	var bets []*Bet
	for i, record := range records {
		if i == 0 {
			continue
		}

		if len(record) < 5 {
			continue
		}

		bet := &Bet{
			FirstName: record[0],
			LastName:  record[1],
			Document:  record[2],
			Birthdate: record[3],
			Number:    record[4],
		}
		bets = append(bets, bet)
	}

	return bets, nil
}
