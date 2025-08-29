#!/bin/bash

TEST_MESSAGE="test_message"

echo "Prueba a echo server: "

RESPONSE=$(docker run --rm --network tp0_testing_net alpine sh -c "
  echo '$TEST_MESSAGE' | nc server 12345
")

if [ "$RESPONSE" = "$TEST_MESSAGE" ]; then
    echo "action: test_echo_server | result: success"
    exit 0
else
    echo "action: test_echo_server | result: fail"
    echo "Enviado: '$TEST_MESSAGE'"
    echo "Recibido: '$RESPONSE'"
    exit 1
fi
