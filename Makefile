MONITORS_XML=~/.config/monitors.xml
GDM_MONITORS_XML=/var/lib/gdm/.config/monitors.xml

sync-gdm:
	@echo "sync monitors.xml to GDM..."
	@sudo cp $(MONITORS_XML) $(GDM_MONITORS_XML)
	@sudo chown gdm:gdm $(GDM_MONITORS_XML)

.PHONY: sync-monitors
