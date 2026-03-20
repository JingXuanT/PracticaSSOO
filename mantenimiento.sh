#!/bin/bash

# CONFIGURACIÓN

BACKUP_RUTA="/home/azureuser/backups"
TIME=$(date +%Y%m%d_%H%M%S)
BACKUP="$BACKUP_RUTA/backup_$TIME.tar.gz"

BACKUP_DIRECCIONES=(
    "/etc/nginx"
    "/etc/supervisor"
    "/var/www/html"
    "/var/www"
    "/home/azureuser"
)

LOG_RUTA="/var/log"
LOG_SAVE_RUTA="/var/log/mantenimiento.log"

write_log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | sudo tee -a "$LOG_SAVE_RUTA"
}

# SCRIPT

if [ ! -d "$BACKUP_RUTA" ]; then
    sudo mkdir -p "$BACKUP_RUTA"
    write_log "Directorio $BACKUP_RUTA creado"
fi

DIRECCIONES_GUARDADAS=()
for dir in "${BACKUP_DIRECCIONES[@]}"; do
    if [ -d "$dir" ]; then
        DIRECCIONES_GUARDADAS+=("$dir")
        write_log "  - Directorio encontrado: $dir"
    else
        write_log "  - Directorio NO encontrado: $dir"
    fi
done

# LIMPIEZA

if [ ${#DIRECCIONES_GUARDADAS[@]} -gt 0 ]; then
    sudo tar -czf "$BACKUP" "${DIRECCIONES_GUARDADAS[@]}" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        write_log "Backup creado: $(basename "$BACKUP")"
        write_log "Tamaño: $(du -h "$BACKUP" | cut -f1)"
    else
        write_log "No se pudo crear el backup"
    fi
else
    write_log "No hay directorios válidos para backup"
fi

write_log "Limpiando backups antiguos"
cd "$BACKUP_RUTA" || exit
ls -t backup_*.tar.gz 2>/dev/null | tail -n +8 | while read old_backup; do
    sudo rm -f "$BACKUP_RUTA/$old_backup"
    write_log "  - Backup antiguo eliminado: $old_backup"
done

LOG_COUNT_BEFORE=$(find "$LOG_RUTA" -type f -name "*.log" -mtime +7 2>/dev/null | wc -l)

sudo find "$LOG_RUTA" -type f -name "*.log" -mtime +7 -delete 2>/dev/null

sudo find "$LOG_RUTA" -type f -name "*.gz" -mtime +7 -delete 2>/dev/null

write_log "Logs eliminados: $LOG_COUNT_BEFORE archivos"

# MONITORIZACIÓN DEL SISTEMA (EXTRA)

DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}')
write_log "Uso de disco: $DISK_USAGE"

FREE_MEMORY=$(free -h | awk 'NR==2 {print $7}')
write_log "Memoria libre: $FREE_MEMORY"

SERVICIOS=("nginx" "supervisor")
for servicio in "${SERVICIOS[@]}"; do
    if systemctl is-active --quiet "$servicio" 2>/dev/null; then
        write_log "Servicio $servicio: ACTIVO"
    else
        write_log "Servicio $servicio: INACTIVO"
    fi
done

LAST_SSH=$(last -n 5 | head -n 5)
write_log "Últimos 5 accesos SSH:"
echo "$LAST_SSH" | while read line; do
    write_log "  $line"
done

write_log "============================================"
write_log "MANTENIMIENTO FINALIZADO"
write_log "============================================"
