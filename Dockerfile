FROM ghcr.io/inti-cmnb/kicad5_auto_full:1.7.0-3_k5.1.9_d11.6
LABEL AUTHOR Salvador E. Tropea <stropea@inti.gob.ar>
LABEL Description="Export various files from KiCad projects (KiCad 5)"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /mnt

ENTRYPOINT [ "/entrypoint.sh" ]
