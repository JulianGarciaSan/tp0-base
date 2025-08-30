import sys

def server_part_setup(f):
    f.write(
    "name: tp0\n"
    "services:\n"
    "  server:\n"
    "    container_name: server\n"
    "    image: server:latest\n"
    "    entrypoint: python3 /main.py\n"
    "    environment:\n"
    "      - PYTHONUNBUFFERED=1\n"
#    "      - LOGGING_LEVEL=DEBUG\n"
    "    networks:\n"
    "      - testing_net\n"
    "    volumes:\n"
    "      - ./server/config.ini:/config.ini\n\n" 
    )

def client_part_setup(f,client_id):
    f.write(
        f"  client{client_id}:\n"
        f"    container_name: client{client_id}\n"
        f"    image: client:latest\n"
        f"    entrypoint: /client\n"
        f"    environment:\n"
        f"      - CLI_ID={client_id}\n"
        f"      - NOMBRE={"Julian" + str(client_id)}\n"
        f"      - APELLIDO={"Garcia" + str(client_id)}\n"
        f"      - DOCUMENTO={client_id}\n"
        f"      - NACIMIENTO={"2000-01-01"}\n"
        f"      - NUMERO={client_id*1000}\n"
#        f"      - CLI_LOG_LEVEL=DEBUG\n"
        f"    networks:\n"
        f"      - testing_net\n"
        f"    depends_on:\n"
        f"      - server\n"
        f"    volumes:\n"
        f"      - ./client/config.yaml:/config.yaml\n\n"
    )

def network_part_setup(f):
    f.write(
        "networks:\n"
        "  testing_net:\n"
        "    ipam:\n"
        "      driver: default\n"
        "      config:\n"
        "        - subnet: 172.25.125.0/24\n"
    )

def setup(f,client_id):
    with open(f, 'w') as f:
        server_part_setup(f)
        for i in range(1,client_id + 1):
            client_part_setup(f,i)
        network_part_setup(f)

def main():
    if len(sys.argv) != 3:
        print("Uso: python mi-generador.py <nombre_archivo> <cantidad_clientes>")
        sys.exit(1)

    nombre_archivo = sys.argv[1]
    cantidad_clientes = int(sys.argv[2])

    setup(nombre_archivo,cantidad_clientes)

if __name__ == "__main__":
    main()