#!/usr/bin/env bash

set -euo pipefail

CONFIG_DIR="$HOME/.config"
SHELL_CONFIG_DIR="$CONFIG_DIR/votu-fieldops"
SHELL_CONFIG_FILE="$SHELL_CONFIG_DIR/environment.sh"
SYSTEMD_ENV_DIR="$CONFIG_DIR/environment.d"
SYSTEMD_ENV_FILE="$SYSTEMD_ENV_DIR/votu-fieldops.conf"
PROFILE_FILE="$HOME/.profile"
SOURCE_LINE='[ -f "$HOME/.config/votu-fieldops/environment.sh" ] && . "$HOME/.config/votu-fieldops/environment.sh"'

mkdir -p "$SHELL_CONFIG_DIR" "$SYSTEMD_ENV_DIR"

cat >"$SHELL_CONFIG_FILE" <<'EOF'
# VOTU FieldOps - configuração persistente da comunicação Raspberry Pi/CLP.
export VOTU_MACHINE_BACKEND=gpio
export VOTU_PULSE_PIN=17
export VOTU_FINISHED_PIN=27
export VOTU_PULSE_SECONDS=0.05
export VOTU_PULSE_GAP_SECONDS=0.05
export VOTU_FINISHED_TIMEOUT=120
export VOTU_OUTPUT_ACTIVE_HIGH=true
export VOTU_FINISHED_ACTIVE_HIGH=true
export VOTU_FINISHED_PULL_UP=false
EOF

cat >"$SYSTEMD_ENV_FILE" <<'EOF'
# VOTU FieldOps - configuração persistente da comunicação Raspberry Pi/CLP.
VOTU_MACHINE_BACKEND=gpio
VOTU_PULSE_PIN=17
VOTU_FINISHED_PIN=27
VOTU_PULSE_SECONDS=0.05
VOTU_PULSE_GAP_SECONDS=0.05
VOTU_FINISHED_TIMEOUT=120
VOTU_OUTPUT_ACTIVE_HIGH=true
VOTU_FINISHED_ACTIVE_HIGH=true
VOTU_FINISHED_PULL_UP=false
EOF

touch "$PROFILE_FILE"
if ! grep -Fqx "$SOURCE_LINE" "$PROFILE_FILE"; then
    printf '\n# VOTU FieldOps\n%s\n' "$SOURCE_LINE" >>"$PROFILE_FILE"
fi

printf '%s\n' \
    "Configuração do VOTU FieldOps gravada com sucesso." \
    "Arquivo do shell: $SHELL_CONFIG_FILE" \
    "Arquivo da sessão gráfica: $SYSTEMD_ENV_FILE" \
    "" \
    "Reinicie a Raspberry ou encerre e abra novamente a sessão para aplicar." \
    "Para aplicar apenas no terminal atual, execute:" \
    "  source \"$SHELL_CONFIG_FILE\""
