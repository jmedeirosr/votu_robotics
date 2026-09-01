# Ligação direta Raspberry Pi → CLP

O software mantém dois modos de comunicação:

- `serial` (padrão): protocolo atual com PIC, enviando `01`, `02`, etc. e
  aguardando `F`;
- `gpio`: envia a posição como quantidade de pulsos e aguarda a entrada de
  finalização do CLP.

## Segurança elétrica

Os GPIOs da Raspberry Pi trabalham em **3,3 V e não toleram 5 V, 12 V ou 24 V**.
Não ligue uma entrada ou saída do CLP diretamente à Raspberry. Use duas vias
isoladas:

1. GPIO de pulsos → optoacoplador/driver → entrada digital do CLP;
2. saída de finalização do CLP → optoacoplador → GPIO de entrada.

O circuito deve assegurar nível lógico definido quando o opto estiver aberto.
Só compartilhe GND se o projeto da interface elétrica exigir; uma interface
optoisolada de verdade normalmente mantém os dois lados separados.

## Configuração

Instale o suporte na Raspberry:

```bash
python -m pip install '.[raspberry]'
```

Antes de iniciar a aplicação:

```bash
export VOTU_MACHINE_BACKEND=gpio
export VOTU_PULSE_PIN=17
export VOTU_FINISHED_PIN=27
export VOTU_PULSE_SECONDS=0.05
export VOTU_PULSE_GAP_SECONDS=0.05
export VOTU_FINISHED_TIMEOUT=120
export VOTU_OUTPUT_ACTIVE_HIGH=true
export VOTU_FINISHED_ACTIVE_HIGH=true
export VOTU_FINISHED_PULL_UP=false
```

Os números dos pinos usam a numeração **BCM**, não a posição física do
conector. Se `VOTU_FINISHED_PULL_UP=true`, a entrada usa o pull-up interno e o
sinal ativo passa a ser nível baixo.

## Premissa do protocolo

Esta primeira implementação representa a posição `N` com `N` pulsos. Antes de
ligar o braço, confirme no programa do CLP:

- se a contagem de pulsos realmente corresponde à posição;
- duração mínima do pulso e do intervalo;
- polaridade das duas linhas;
- se o sinal de finalização retorna ao estado inativo antes do próximo POT.

Faça o primeiro ensaio com as saídas de movimento do braço desabilitadas e um
analisador lógico ou os diagnósticos online do CLP.
