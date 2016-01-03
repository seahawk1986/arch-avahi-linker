### Internationalization (I18N):

PODIR     = ./
PREFIX   ?= /usr/
LOCDIR    = $(PREFIX)/share/locale
LOCALEDIR = $(DESTDIR)/$(LOCDIR)
I18Npo    = $(wildcard $(PODIR)/*.po)
I18Nmsgs  = $(addprefix $(LOCDIR)/, $(addsuffix /LC_MESSAGES/avahi-linker.mo, $(notdir $(foreach file, $(I18Npo), $(basename $(file))))))
I18Npot   = $(PODIR)/vdr-addon-avahi-linker.pot

all:
	@echo "Done."


i18n: $(I18Nmsgs)

%.mo: %.po
	msgfmt -c -o $@ $<

%.po: $(PODIR)/vdr-addon-avahi-linker.pot
	msgmerge -U --no-wrap --no-location --backup=none -q $@ $<
	@touch $@

$(I18Nmsgs): $(LOCDIR)/%/LC_MESSAGES/avahi-linker.mo: $(PODIR)/%.mo
	@mkdir -p $(dir $@)
	echo cp $< $@
	cp $< $@

install-i18n:
	@mkdir -p $(LOCALEDIR)
	@(cd $(LOCALEDIR); cp -r --parents * $(LOCALEDIR))

install: i18n

clean:
	@rm -f *.mo
