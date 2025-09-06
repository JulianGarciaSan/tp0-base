package common

import (
	"bufio"
	"encoding/csv"
	"fmt"
	"io"
	"os"
	"strings"
)

type BetScanner struct {
	file    *os.File
	scanner *bufio.Scanner
}

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
	for _, record := range records {
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

func (cp *ClientProtocol) NewBetScanner(filePath string) (*BetScanner, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("error opening file: %v", err)
	}

	scanner := bufio.NewScanner(file)

	return &BetScanner{
		file:    file,
		scanner: scanner,
	}, nil
}

func (bs *BetScanner) ReadNextBet() (*Bet, error) {
	for bs.scanner.Scan() {
		line := strings.TrimSpace(bs.scanner.Text())

		if line == "" {
			continue
		}

		fields := strings.Split(line, ",")

		if len(fields) != 5 {
			continue
		}

		for i := range fields {
			fields[i] = strings.TrimSpace(fields[i])
		}

		if fields[0] == "" || fields[1] == "" || fields[2] == "" ||
			fields[3] == "" || fields[4] == "" {
			continue
		}

		bet := &Bet{
			FirstName: fields[0],
			LastName:  fields[1],
			Document:  fields[2],
			Birthdate: fields[3],
			Number:    fields[4],
		}

		return bet, nil
	}

	if err := bs.scanner.Err(); err != nil {
		return nil, fmt.Errorf("error scanning file: %v", err)
	}

	return nil, io.EOF
}

func (bs *BetScanner) Close() error {
	if bs.file != nil {
		return bs.file.Close()
	}
	return nil
}
