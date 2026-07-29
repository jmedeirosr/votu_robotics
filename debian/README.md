# VOTU FieldOps

Aplicação desktop para planejamento, visualização e transmissão do mapa de plantio.

## Executar durante o desenvolvimento

```bash
uv run python src/interface.py
```

## Gerar o pacote para Raspberry Pi 4

O build precisa ser realizado em Raspberry Pi OS 64-bit (`aarch64`) compatível com as
máquinas de destino, pois um binário Linux não é universal entre arquiteturas.

```bash
chmod +x packaging/build.sh installer/*.sh
./packaging/build.sh
```

O resultado é `release/votu-fieldops-rpi4-aarch64.tar.gz`. Para instalar em outra
Raspberry Pi:

1. copie o arquivo para a máquina;
2. extraia o `.tar.gz`;
3. abra a pasta `votu-fieldops-installer`;
4. execute `install.sh` (duplo clique e escolha **Executar**, ou use
   `./install.sh` no terminal).

O assistente gráfico instala apenas para o usuário atual, sem `sudo`, e permite
escolher, em etapas, se deve criar uma entrada no menu e um ícone na área de
trabalho. Dados exportados ficam em
`~/.local/share/votu-fieldops/mapas` e logs em
`~/.local/state/votu-fieldops/erros.log`.

Para remover o aplicativo, execute `uninstall.sh`. O assistente permite escolher
os componentes a remover; mapas, configurações e logs são preservados por padrão.
