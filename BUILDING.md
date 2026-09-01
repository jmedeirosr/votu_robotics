# Build e distribuição do Votu FieldOps

O comando oficial para gerar uma release completa é:

```bash
make release
```

Ele valida o projeto, executa testes, compila a aplicação com Nuitka, cria o
pacote Debian, cria o Wizard gráfico QtIFW e produz os metadados em `output/`.

## Regra de compatibilidade

Nuitka produz binários nativos. Cada artefato deve ser construído no sistema
mais antigo que irá executá-lo e na mesma arquitetura do destino:

| Destino | Ambiente de build |
|---|---|
| Raspberry Pi OS Bullseye 32-bit | Bullseye ARMv7 (`armhf`) |
| Raspberry Pi OS Bullseye 64-bit | Bullseye ARM64 (`arm64`) |
| Raspberry Pi OS Bookworm 64-bit | Bookworm ARM64 (`arm64`) |
| Ubuntu ARM64 | Ubuntu ARM64 compatível |

Um binário compilado no Bookworm não deve ser publicado como compatível com
Bullseye. O pipeline não faz cross-compilation entre ARMv7 e ARM64.

## Pré-requisitos do host

- Python 3.12 ou 3.13 (Python 3.14 ainda é experimental no Nuitka);
- compilador GCC e ferramentas de desenvolvimento;
- `dpkg-deb`;
- Nuitka;
- Qt Installer Framework com `binarycreator` disponível no `PATH`;
- bibliotecas de desenvolvimento usadas pelo PyQt6.

Em Raspberry Pi OS:

```bash
sudo apt update
sudo apt install build-essential patchelf dpkg-dev libgl1 libegl1 \
  libxkbcommon-x11-0 libxcb-cursor0
python -m pip install -e '.[build]'
```

O Qt Installer Framework precisa ser instalado ou compilado para a mesma
arquitetura do host. Defina o `PATH` antes do build:

```bash
export PATH="/opt/Qt/Tools/QtInstallerFramework/bin:$PATH"
```

## Comandos

```bash
make validate
make test
make debug
make release
make nightly
make clean
```

Para diagnosticar o pipeline sem Nuitka/QtIFW:

```bash
python release.py --dry-run
```

Para produzir somente o `.deb` quando o QtIFW ainda não estiver instalado:

```bash
python release.py --skip-installer
```

`--skip-build` só deve ser usado quando `build/stage/app` já contém o resultado
standalone da mesma versão e arquitetura.

## Artefatos

Uma release completa gera:

```text
output/
├── VotuFieldOps-VERSAO-ARQUITETURA.deb
├── VotuFieldOps-VERSAO-ARQUITETURA.run
├── release.json
├── manifest.json
├── SHA256SUMS
└── CHANGELOG.md
```

O pacote Debian instala a aplicação em `/opt/votu-fieldops`, o launcher em
`/usr/bin/votu-fieldops` e a entrada de menu em
`/usr/share/applications/votu-fieldops.desktop`.

Dados e logs graváveis permanecem no diretório do usuário:

- dados: `${XDG_DATA_HOME:-~/.local/share}/votu-fieldops`;
- logs: `${XDG_STATE_HOME:-~/.local/state}/votu-fieldops`.

## Versão e publicação

A versão é lida exclusivamente de `src/version.py`. Antes de publicar:

1. altere `__version__`;
2. atualize `CHANGELOG.md`;
3. execute `make release`;
4. valide `SHA256SUMS`;
5. publique todos os arquivos de `output/`.

Para preencher URLs absolutas em `release.json`:

```bash
RELEASE_BASE_URL="https://downloads.exemplo.com/votu-fieldops" make release
```

Para builds reproduzíveis, o CI deve definir `SOURCE_DATE_EPOCH` com o timestamp
do commit.
