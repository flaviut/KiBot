FROM setsoft/kicad_auto:10.4-5.1.9
LABEL AUTHOR Salvador E. Tropea <stropea@inti.gob.ar>
LABEL Description="Export various files from KiCad projects (KiCad 5)"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /mnt

ENTRYPOINT [ "/entrypoint.sh" ]
