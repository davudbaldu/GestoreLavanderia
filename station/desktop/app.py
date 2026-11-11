"""Two native Windows entry points, with a shared authenticated station core.

The packaged apps deliberately start in collaudo. No generic keyboard/stdin
adapter is advertised as a connection to an RFID reader. A vendor adapter must
be implemented and validated before enabling production hardware.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from queue import Queue, Empty
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    tk=None
    ttk=messagebox=None
if tk is not None:
    from . import pulito_style as visual
from .config import backend_config, data_directory, Preferences
from .credentials import TokenStore, _crypt
from .cloud import CloudAPI, CloudError
from . import startup
from .labels import render_labels
from .diagnostics import collect as collect_diagnostics
from .hardware import profile_from_settings, probe_reader, ProbeError, serial_available
from .live_reader import LiveSerialReader
from .operator_messages import blocked_read_message
from threading import Event
import webbrowser
from outbox import ReadOutbox


OUTCOMES={'accettata':'Capo riconosciuto','ripetizione':'Ripetuto · non conteggiato','tag_sconosciuto':'Tag da identificare','tag_non_valido':'Codice non valido','tag_ambiguo':'Tag da verificare','cliente_diverso':'Capo di altra struttura','archivio_diverso':'Tipo di capo diverso','identita_da_verificare':'Assegnatario da verificare','altro_armadio':'Capo già in un altro armadio','armadio_pieno':'Armadio pieno','sessione_chiusa':'Sessione già chiusa'}


class InstanceLock:
    def __init__(self, path):
        self.file = open(path, 'a+b')
        self.file.seek(0); self.file.write(b'1'); self.file.flush(); self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('Questa postazione è già aperta su questo PC.') from None

    def close(self):
        self.file.close()


class StationApp:
    def __init__(self, kind, root, directory=None):
        self.kind=kind; self.root=root; self.directory=Path(directory or data_directory(kind))
        self.preferences=Preferences(self.directory); self.store=TokenStore(self.directory)
        self.outbox=ReadOutbox(self.directory/'observations.sqlite3'); self.api=CloudAPI(backend_config())
        self.pool=ThreadPoolExecutor(max_workers=1); self.busy=False; self.stopped=False
        self.after_jobs=set()
        self.session=None; self.snapshot=None; self.before=None; self.remember=False; self.labels=[];self.probe_stop=None;self.probe_window=None
        self.live_reader=None; self.reader_events=Queue(); self.last_scanned_tag=None; self.next_refresh_at=0.0
        self.root.title(('Sporco' if kind=='sporco' else 'Pulito')+' · Gestore Lavanderia · COLLAUDO')
        self.root.geometry('1180x860'); self.root.minsize(920,680); self.root.configure(bg='#f3f6fb')
        style=ttk.Style(); style.theme_use('clam')
        style.configure('TFrame',background='#f3f6fb');style.configure('TLabel',background='#f3f6fb',foreground='#213750',font=('Segoe UI',10))
        style.configure('Title.TLabel',font=('Segoe UI',24,'bold'));style.configure('Status.TLabel',font=('Segoe UI',11))
        style.configure('TButton',font=('Segoe UI',10),padding=9);style.configure('TEntry',padding=7)
        if kind=='pulito':visual.configure_theme(root)
        self.status=tk.StringVar(value='Accedi al gestionale per collegare questa postazione.')
        self.global_header=ttk.Label(root,text='GESTORE LAVANDERIA · '+kind.upper(),style='Title.TLabel')
        self.global_header.pack(anchor='w',padx=24,pady=(20,6))
        self.global_mode=ttk.Label(root,text='COLLAUDO · antenna da verificare sul PC · stampa diretta non attiva',foreground='#966416')
        self.global_mode.pack(anchor='w',padx=24)
        self.body=ttk.Frame(root);self.body.pack(fill='both',expand=True,padx=24,pady=18)
        self.global_status=ttk.Label(root,textvariable=self.status,style='Status.TLabel',wraplength=1120)
        self.global_status.pack(fill='x',padx=24,pady=(0,18))
        self.show_login();self.root.protocol('WM_DELETE_WINDOW',self.shutdown)
        if self.store.path.exists():
            self.run(self.restore,self.show_station)
        self.later(100,self.poll)

    def later(self, delay, callback):
        def invoke():
            self.after_jobs.discard(handle)
            if not self.stopped:callback()
        handle=self.root.after_idle(invoke) if delay is None else self.root.after(delay,invoke)
        self.after_jobs.add(handle)

    def run(self, work, done):
        if self.busy or self.stopped:return
        self.busy=True
        future=self.pool.submit(work)
        def check():
            if self.stopped:return
            if not future.done():self.later(80,check);return
            self.busy=False
            try:
                value=future.result()
                if self.remember and self.api.refresh_token:
                    self.store.save(self.api.refresh_token)
                done(value)
            except Exception as error:
                self.status.set(str(error))
                self.operator_error(str(error))
        self.later(80,check)

    def restore(self):
        self.api.refresh(self.store.load());self.remember=True
        return self.api.lists()

    def clear_body(self):
        for child in self.body.winfo_children():child.destroy()

    def show_login(self):
        self.clear_body()
        modern=self.kind=='pulito'
        if modern:
            self.global_header.pack_forget();self.global_mode.pack_forget()
            visual.brand(self.body,tk.StringVar(value='Gestore Lavanderia · Postazione Windows'))
            card=visual.Panel(self.body,width=490,height=420,padding=30)
            card.pack(anchor='n',pady=(30,12))
            frame=card.content
            def label(text,**options):return tk.Label(frame,text=text,bg='white',fg=visual.INK,**options)
            label('Accedi al gestionale',font=('Segoe UI',-27,'bold')).pack(anchor='w',pady=(0,8))
            tk.Label(frame,text='Collega la postazione al tuo archivio.',font=('Segoe UI',-14),bg='white',fg=visual.MUTED).pack(anchor='w',pady=(0,24))
        else:
            frame=ttk.Frame(self.body);frame.pack(anchor='n',pady=45)
            def label(text,**options):return ttk.Label(frame,text=text,**options)
            label('Collega il gestionale online',font=('Segoe UI',17,'bold')).pack(anchor='w',pady=12)
        label('Email').pack(anchor='w');email=ttk.Entry(frame,width=48);email.pack(fill='x',pady=(5,18))
        label('Password').pack(anchor='w');password=ttk.Entry(frame,show='•',width=48);password.pack(fill='x',pady=(5,18))
        remember=tk.BooleanVar(value=False)
        ttk.Checkbutton(frame,text='Ricorda la sessione su questo PC',variable=remember,style='Card.TCheckbutton' if modern else 'TCheckbutton',state='normal' if os.name=='nt' else 'disabled').pack(anchor='w',pady=(0,14))
        def login():
            mail=email.get().strip();secret=password.get();password.delete(0,'end');self.remember=remember.get()
            self.status.set('Collegamento in corso…')
            def work():
                self.api.login(mail,secret)
                if not self.remember:self.store.clear()
                return self.api.lists()
            self.run(work,self.show_station)
        if modern:visual.Button(frame,text='Accedi',command=login,primary=True).pack(fill='x')
        else:ttk.Button(frame,text='Accedi',command=login).pack(anchor='w',pady=10)
        password.bind('<Return>',lambda _:login())
        tools=ttk.Frame(self.body) if modern else frame
        if modern:
            tools.pack(anchor='n',pady=12)
            ttk.Label(tools,text='STRUMENTI DI COLLAUDO',foreground=visual.MUTED,font=('Segoe UI',-11,'bold')).pack(pady=(0,8))
        def tool(text,command):
            if modern:return visual.Button(tools,text=text,command=command,width=360)
            return ttk.Button(tools,text=text,command=command)
        tool('Rileva lettori e stampanti',self.diagnostics).pack(fill='x',pady=4)
        if self.kind=='pulito':tool('Prova lettore dell’armadio',self.hardware_probe).pack(fill='x',pady=4)
        tool('Installa su questo PC e avvia con Windows',self.install).pack(fill='x',pady=4)
        if modern:self.warning(self.body).pack(fill='x',side='bottom',pady=(12,0))

    def warning(self, parent, text=None):
        card=visual.Panel(parent,fill='#fff7e5',border='#efdda4',padding=12,radius=12,height=44)
        card.message=text if text is not None else tk.StringVar(value='COLLAUDO · antenna da verificare sul PC · stampa diretta Zebra non attiva')
        label=tk.Label(card.content,textvariable=card.message,
                       bg='#fff7e5',fg='#805d19',font=('Segoe UI',-13),anchor='w')
        label.pack(fill='both',expand=True)
        return card

    def set_operator_mode(self, mode):
        self.operator_mode=mode
        fill=visual.HERO[mode]
        self.hero.recolor(fill)
        self.hero_stack.configure(bg=fill)
        for label in (self.hero_label,self.slot_banner,self.person_label,self.detail_label):
            label.configure(bg=fill,fg='white')
        self.fit_instruction()

    def show_station(self, data):
        stations,self.clients,self.open_sessions=data;self.stations=[s for s in stations if s['kind']==self.kind]
        if not self.stations or not self.clients:raise CloudError('Nessuna postazione o struttura configurata.')
        self.clear_body()
        if self.kind=='pulito':
            self.global_header.pack_forget();self.global_mode.pack_forget();self.global_status.pack_forget()
            self.operator_area=tk.Frame(self.body,bg=visual.PAGE);self.operator_area.pack(fill='both',expand=True)
            self.admin_area=ttk.Frame(self.body)
            panel=self.admin_area
            self.operator_context=tk.StringVar(value='Seleziona cliente e archivio dal menu')
            visual.brand(self.operator_area,self.operator_context,menu=self.toggle_admin)
            card=visual.Panel(self.operator_area,height=246)
            self.hero_card=card
            card.pack(fill='x',pady=(0,18))
            self.hero=visual.Panel(card.content,fill=visual.HERO['idle'],border=visual.HERO['idle'],radius=18,padding=14)
            self.hero.pack(fill='both',expand=True)
            self.hero_stack=tk.Frame(self.hero.content,bg=visual.HERO['idle'])
            self.hero_stack.place(relx=.5,rely=.5,anchor='center',relwidth=1)
            self.hero_overline=tk.StringVar(value='PRONTO ALLA LETTURA')
            self.hero_label=tk.Label(self.hero_stack,textvariable=self.hero_overline,font=('Segoe UI',-13,'bold'))
            self.hero_label.pack()
            self.instruction=tk.StringVar(value='—')
            self.slot_banner=tk.Label(self.hero_stack,textvariable=self.instruction,font=('Segoe UI',-86,'bold'),anchor='center')
            self.slot_banner.pack(fill='x',pady=4)
            self.hero_stack.bind('<Configure>',lambda event:self.fit_instruction(event.width))
            self.instruction.trace_add('write',lambda *_:self.fit_instruction())
            self.operator_person=tk.StringVar(value='Passa il primo indumento')
            self.person_label=tk.Label(self.hero_stack,textvariable=self.operator_person,font=('Segoe UI',-24,'bold'))
            self.person_label.pack()
            self.scan_detail=tk.StringVar(value='La casella apparirà automaticamente, senza tasto di conferma.')
            self.detail_label=tk.Label(self.hero_stack,textvariable=self.scan_detail,font=('Segoe UI',-18),wraplength=1040)
            self.detail_label.pack(pady=(6,0))
            self.set_operator_mode('idle')
            self.operator_note=tk.StringVar(value='COLLAUDO · antenna da verificare · stampa diretta Zebra non attiva')
            self.operator_warning=self.warning(self.operator_area,self.operator_note)
            self.operator_warning.pack(side='bottom',fill='x',pady=(12,0))
            self.map_card=visual.Panel(self.operator_area)
            self.map_card.pack(fill='both',expand=True)
            legend=tk.Frame(self.map_card.content,bg='white');legend.pack(fill='x',pady=(0,8))
            tk.Label(legend,text='Le caselle utilizzate restano evidenziate.',bg='white',fg='#70838d',font=('Segoe UI',-13)).pack(side='left')
            for text,color in [('Ultima','#087c70'),('Occupata','#66c8b4'),('Libera','#cddde2')]:
                key=tk.Frame(legend,bg='white');key.pack(side='right',padx=6)
                tk.Label(key,text='■',bg='white',fg=color,font=('Segoe UI',-12)).pack(side='left')
                tk.Label(key,text=text,bg='white',fg='#758895',font=('Segoe UI',-12)).pack(side='left')
            self.grid=tk.Frame(self.map_card.content,bg='white');self.grid.pack(fill='both',expand=True)
            self.active_slot=None;self.slot_widgets={};self.slot_styles={}
        else:
            panel=self.body
            self.instruction=tk.StringVar(value='In attesa di una lettura confermata dal server.')
        if self.kind=='pulito':
            menu_actions=ttk.Frame(panel);menu_actions.pack(fill='x',pady=(3,12))
            visual.Button(menu_actions,text='← Casellario',command=self.toggle_admin,width=145).pack(side='left',padx=(0,12))
            visual.Button(menu_actions,text='Chiudi armadio e prepara etichette',command=self.close_session,width=300,primary=True).pack(side='left',padx=(0,12))
            visual.Button(menu_actions,text='Rivedi etichette',command=self.show_labels,width=155).pack(side='left')
        top=ttk.Frame(panel);top.pack(fill='x')
        names=[s['name'] for s in self.stations]
        self.station_choice=ttk.Combobox(top,values=names,state='readonly',width=22);self.station_choice.pack(side='left',padx=(0,12))
        previous=self.preferences.data.get('station_id');self.station_choice.current(next((i for i,s in enumerate(self.stations) if s['id']==previous),0))
        self.client_choice=ttk.Combobox(top,values=[c['name']+' · '+c['site'] for c in self.clients],state='readonly',width=32);self.client_choice.current(0);self.client_choice.pack(side='left',padx=(0,12))
        self.archive_choice=ttk.Combobox(top,values=['Tutti i capi della struttura','Ospiti · capi personali','Operatori · divise'],state='readonly',width=26);self.archive_choice.current(1 if self.kind=='pulito' else 0);self.archive_choice.pack(side='left')
        self.empty=tk.BooleanVar(value=False)
        if self.kind=='pulito':ttk.Checkbutton(panel,text='Confermo che tutte le caselle sono state svuotate prima di iniziare.',variable=self.empty).pack(anchor='w',pady=(16,2))
        controls=ttk.Frame(panel);controls.pack(fill='x',pady=12)
        ttk.Button(controls,text='Apri sessione di collaudo',command=self.start).pack(side='left')
        ttk.Button(controls,text='Riprendi sessione aperta',command=self.resume).pack(side='left',padx=10)
        ttk.Button(controls,text='Rileva dispositivi',command=self.diagnostics).pack(side='left',padx=10)
        if self.kind=='pulito':ttk.Button(controls,text='Prova lettore',command=self.hardware_probe).pack(side='left',padx=4)
        ttk.Button(controls,text='Installa su questo PC e avvia con Windows',command=self.install).pack(side='right')
        if self.kind=='pulito':
            reader_controls=ttk.Frame(panel);reader_controls.pack(fill='x',pady=7)
            ttk.Button(reader_controls,text='Avvia lettura continua · senza LED',command=self.start_live_reader).pack(side='left')
            ttk.Button(reader_controls,text='Ferma lettura',command=self.stop_live_reader).pack(side='left',padx=12)
            ttk.Label(reader_controls,text='COLLAUDO: non sostituisce NewPod in produzione.').pack(side='left',padx=8)
        self.context=tk.StringVar(value='Scegli struttura e postazione. L’identità della postazione rimane memorizzata su questo PC.')
        ttk.Label(panel,textvariable=self.context,wraplength=1100).pack(anchor='w',pady=8)
        scan=ttk.Frame(panel);scan.pack(fill='x',pady=8)
        ttk.Label(scan,text='Tag di prova (uno alla volta sul pulito; separati da spazi o righe sullo sporco)').pack(anchor='w')
        self.tag_input=ttk.Entry(scan);self.tag_input.pack(side='left',fill='x',expand=True,pady=8)
        ttk.Button(scan,text='Invia prova',command=self.capture).pack(side='right',padx=(12,0));self.tag_input.bind('<Return>',lambda _:self.capture())
        if self.kind!='pulito':
            ttk.Label(panel,textvariable=self.instruction,font=('Segoe UI',22,'bold'),wraplength=1080).pack(anchor='w',pady=10)
        self.counts=tk.StringVar(value='');ttk.Label(panel,textvariable=self.counts).pack(anchor='w',pady=4)
        if self.kind!='pulito':
            self.grid=ttk.Frame(panel);self.grid.pack(fill='x',pady=8)
        log=ttk.Frame(panel);log.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(log,columns=('tag','client','name','outcome','slot'),show='headings',height=7)
        for name,width in [('tag',200),('client',210),('name',220),('outcome',220),('slot',65)]:self.tree.heading(name,text={'tag':'Tag','client':'Struttura del capo','name':'Nominativo','outcome':'Esito','slot':'Casella'}[name]);self.tree.column(name,width=width,minwidth=65)
        scrollbar=ttk.Scrollbar(log,orient='vertical',command=self.tree.yview);self.tree.configure(yscrollcommand=scrollbar.set);scrollbar.pack(side='right',fill='y');self.tree.pack(fill='both',expand=True)
        pages=ttk.Frame(panel);pages.pack(fill='x',pady=8)
        ttk.Button(pages,text='Più recenti',command=lambda:self.page(None)).pack(side='left');ttk.Button(pages,text='Precedenti',command=self.older).pack(side='left',padx=10)
        ttk.Button(pages,text='Etichette della sessione',command=self.show_labels).pack(side='right')
        self.note=ttk.Entry(panel);self.note.pack(fill='x',pady=4);self.note.insert(0,'')
        ttk.Label(panel,text='Nota di chiusura: obbligatoria se ci sono capi segnalati da separare.').pack(anchor='w')
        self.placed=tk.BooleanVar(value=False)
        if self.kind=='pulito':ttk.Checkbutton(panel,text='Confermo che i capi accettati sono nelle caselle indicate.',variable=self.placed).pack(anchor='w',pady=6)
        ttk.Button(panel,text='Chiudi armadio e prepara etichette' if self.kind=='pulito' else 'Termina sessione sporco',command=self.close_session).pack(anchor='w',pady=6)
        if self.kind=='pulito':
            ttk.Label(panel,textvariable=self.status,style='Status.TLabel',wraplength=1100).pack(anchor='w',pady=6)
            self.render_operator_grid([],90)
        self.status.set('Collegato al gestionale. Modalità collaudo: nessuna lettura proviene ancora dall’antenna.')

    def toggle_admin(self):
        if self.kind!='pulito' or not hasattr(self,'operator_area'):return
        if self.operator_area.winfo_manager():
            self.operator_area.pack_forget()
            self.admin_area.pack(fill='both',expand=True)
        else:
            self.admin_area.pack_forget()
            self.operator_area.pack(fill='both',expand=True)

    def render_operator_grid(self, slots, capacity):
        """Paint only changed caselles; avoid flashing 90 widgets on every server refresh."""
        if self.kind!='pulito':return
        if not hasattr(self,'slot_widgets'):
            self.slot_widgets={}
            self.slot_styles={}
        by_slot={int(s['slot']):s for s in slots}
        capacity=min(capacity or 90,90)
        for index in range(capacity):
            number=index+1
            slot=by_slot.get(number)
            active=self.active_slot==number
            tile_state='active' if active else ('used' if slot else 'free')
            value=str(number).zfill(2)
            style=(value,tile_state)
            cell=self.slot_widgets.get(number)
            if cell is None:
                cell=visual.Slot(self.grid,text=value,state=tile_state)
                row=(index%30)//5
                col=(index//30)*5+((index%30)%5)
                cell.grid(row=row,column=col,sticky='nsew',padx=(7 if col in (5,10) else 2,2),pady=2)
                self.slot_widgets[number]=cell
            elif self.slot_styles.get(number)!=style:
                cell.set_state(value,tile_state)
            self.slot_styles[number]=style
        for col in range(15):self.grid.columnconfigure(col,weight=1,uniform='caselle')
        for row in range(6):self.grid.rowconfigure(row,weight=1,uniform='file')

    def operator_error(self, message):
        """Show a visible stop condition instead of silently leaving the last valid slot lit."""
        if self.kind!='pulito' or not hasattr(self,'slot_banner'):return
        self.active_slot=None
        self.instruction.set('FERMA IL CAPO')
        self.hero_overline.set('PROBLEMA DI LETTURA O COLLEGAMENTO')
        self.operator_person.set('Non riporre il capo')
        self.scan_detail.set('Problema di lettura o collegamento: '+str(message)[:190])
        self.set_operator_mode('bad')
        if self.snapshot:
            self.render_operator_grid(self.snapshot.get('slots') or [],self.session.get('slot_count') if self.session else 90)

    def fit_instruction(self, width=None):
        """Keep explicit two-line errors inside the banner at smaller window sizes."""
        from tkinter.font import Font
        width=max(600,(width or self.hero_stack.winfo_width())-32)
        size=60 if getattr(self,'operator_mode','idle')=='bad' else 86
        font=Font(self.root,family='Segoe UI',size=-size,weight='bold')
        lines=self.instruction.get().splitlines() or ['']
        while size>22 and max(font.measure(line) for line in lines)>width:
            size-=2
            font.configure(size=-size)
        self.slot_banner.configure(font=('Segoe UI',-size,'bold'))
        if hasattr(self,'detail_label'):
            self.detail_label.configure(wraplength=width)
            self.person_label.configure(wraplength=width)
        if not getattr(self,'hero_fit_pending',False):
            self.hero_fit_pending=True
            self.later(None,self.fit_hero_card)

    def fit_hero_card(self):
        self.hero_fit_pending=False
        if self.stopped or not self.hero_card.winfo_exists():return
        # Match the web's min-height: grow for multiline errors and wrapped names.
        height=max(236,self.hero_stack.winfo_reqheight()+64)
        if self.hero_card.winfo_reqheight()!=height:
            self.hero_card.configure(height=height)

    def station(self):return self.stations[self.station_choice.current()]

    def start(self):
        if self.busy:return
        if self.outbox.pending():self.status.set('Sincronizza le letture in attesa prima di cambiare sessione.');return
        station=self.station();client=self.clients[self.client_choice.current()]
        if self.kind=='pulito' and not self.empty.get():self.status.set('Conferma prima che l’armadio sia stato svuotato.');return
        arguments={'p_station':station['id'],'p_client':client['id'],'p_archive':['tutti','ospiti','divise'][self.archive_choice.current()],'p_mode':'collaudo','p_empty':self.kind=='pulito' and self.empty.get()}
        try:pending=self.preferences.open_command(arguments)
        except ValueError as error:self.status.set(str(error));return
        def work():
            result=self.api.rpc('rf_start_session',p_id=pending['id'],**arguments)
            self.preferences.save(pending_open=None,last_session=result['id'])
            return self.api.snapshot(result['id'])
        self.run(work,self.display)

    def resume(self):
        station=self.station()
        def work():
            _,_,sessions=self.api.lists()
            current=next((s for s in sessions if s['station_id']==station['id']),None)
            if not current:raise CloudError('Nessuna sessione aperta per questa postazione.')
            return self.api.snapshot(current['id'])
        self.before=None;self.run(work,self.display)

    def capture(self):
        if self.busy:return
        if not self.session or self.session['status']!='aperta':self.status.set('Apri o riprendi una sessione prima della lettura.');return
        raw=self.tag_input.get().strip();tags=[raw] if self.kind=='pulito' else raw.replace(',',' ').replace(';',' ').split()
        if not tags or not raw or len(tags)>500 or any(len(tag)>256 for tag in tags):self.status.set('Inserisci da 1 a 500 tag di prova.');return
        for tag in tags:self.outbox.enqueue(self.session['id'],self.kind,tag,metadata={'source':'collaudo_manuale','station_kind':self.kind})
        self.tag_input.delete(0,'end');self.before=None
        if self.kind=='pulito':
            self.last_scanned_tag=tags[0].strip().upper()
            self.active_slot=None
            if self.snapshot:self.render_operator_grid(self.snapshot.get('slots') or [],self.session.get('slot_count') if self.session else 90)
            self.instruction.set('VERIFICA IN CORSO')
            self.hero_overline.set('ATTENDI LA CONFERMA')
            self.operator_person.set('Non riporre ancora il capo')
            self.scan_detail.set('Attendi l’assegnazione confermata. Non riporre ancora il capo.')
            self.set_operator_mode('warn')
        else:self.instruction.set('Letture salvate localmente; invio al gestionale…')
        self.sync()

    def sync(self):
        if self.busy:return
        def work():
            if self.outbox.pending():self.outbox.sync_once(self.api.read_batch)
            return self.api.snapshot(self.session['id'],self.before) if self.session else None
        self.run(work,self.display)

    def display(self, data):
        if not data:raise CloudError('Sessione non disponibile.')
        previous=self.snapshot['counts']['accepted'] if self.snapshot else None;was_open=bool(self.session and self.session['status']=='aperta')
        self.snapshot=data;self.session=data['session'];self.preferences.save(last_session=self.session['id'],station_id=self.session['station_id'],pending_open=None)
        self.station_choice.current(next(i for i,s in enumerate(self.stations) if s['id']==self.session['station_id']))
        self.client_choice.current(next(i for i,c in enumerate(self.clients) if c['id']==self.session['client_id']))
        self.archive_choice.current(['tutti','ospiti','divise'].index(self.session['archive']))
        if was_open and self.session['status']=='chiusa':self.empty.set(False);self.placed.set(False)
        for field in [self.station_choice,self.client_choice,self.archive_choice]:field.configure(state='disabled' if self.session['status']=='aperta' else 'readonly')
        self.context.set(data['station']['name']+' · '+data['client']['name']+' · '+data['client']['site']+' · '+self.session['archive']+' · '+self.session['status'])
        counts=data['counts'];occupied=len(data['slots']);capacity=self.session['slot_count'] or 0
        self.counts.set(f"Letture {counts['reads']} · Capi {counts['accepted']} · Ripetute {counts['duplicates']} · Segnalate {counts['blocked']} · Movimenti {counts['movements']} · Da inviare {self.outbox.pending()}"+(f' · Caselle {occupied}/{capacity}' if self.kind=='pulito' else ''))
        if previous is not None and previous!=counts['accepted']:self.placed.set(False)
        self.tree.delete(*self.tree.get_children())
        for read in data['reads']:self.tree.insert('', 'end', values=(read['tag'],' · '.join(filter(None,[read['snapshot'].get('client'),read['snapshot'].get('site')])) or 'Da identificare',read['snapshot'].get('name','—'),OUTCOMES.get(read['outcome'],read['outcome']),read['slot'] or '—'))
        if self.kind=='pulito':
            last_read=data['reads'][0] if data['reads'] else None
            self.active_slot=(last_read['slot'] if last_read and not self.outbox.pending() and
                last_read['outcome'] in ('accettata','ripetizione') and
                (not self.last_scanned_tag or last_read['tag']==self.last_scanned_tag) else None)
            self.operator_context.set(data['client']['name']+' · '+data['client']['site']+' · '+{
                'ospiti':'OSPITI','divise':'DIVISE OPERATORI','tutti':'OSPITI + DIVISE'
            }.get(self.session['archive'],self.session['archive'].upper()))
        if self.kind=='pulito':
            pending=self.outbox.pending()
            if self.session['status']=='chiusa':
                self.instruction.set('ARMADIO CHIUSO')
                self.hero_overline.set('SESSIONE TERMINATA')
                self.operator_person.set(str(occupied)+' caselle pronte')
                self.scan_detail.set(f"Movimenti: {counts['movements']} · Etichette pronte: {counts['labels']}.")
                self.set_operator_mode('closed')
            elif pending or (self.last_scanned_tag and data['reads'] and data['reads'][0]['tag']!=self.last_scanned_tag):
                self.instruction.set('VERIFICA IN CORSO')
                self.hero_overline.set('ATTENDI LA CONFERMA')
                self.operator_person.set('Non riporre ancora il capo')
                self.scan_detail.set('In attesa della conferma del server. Non riporre ancora il capo.')
                self.set_operator_mode('warn')
            elif data['reads']:
                last=data['reads'][0]
                if last['slot'] and last['outcome'] in ('accettata','ripetizione'):
                    self.instruction.set('CASELLA '+str(last['slot']).zfill(2))
                    self.hero_overline.set('LETTURA GIÀ REGISTRATA' if last['outcome']=='ripetizione' else 'DESTINAZIONE CONFERMATA')
                    self.operator_person.set(last['snapshot'].get('name') or 'Capo riconosciuto')
                    self.scan_detail.set(' · '.join(filter(None,[
                        last['snapshot'].get('article'),
                        last['snapshot'].get('department'),
                        'Piano '+str(last['snapshot']['floor']) if last['snapshot'].get('floor') else None])))
                    self.set_operator_mode('ok')
                else:
                    title,detail=blocked_read_message(last['outcome'],last.get('snapshot'))
                    self.instruction.set(title)
                    self.hero_overline.set('FERMA IL CAPO')
                    self.operator_person.set('Proprietario non identificabile' if last['outcome']=='tag_sconosciuto' else 'Capo da separare')
                    self.scan_detail.set(detail)
                    self.set_operator_mode('bad')
            else:
                self.instruction.set('—')
                self.hero_overline.set('PRONTO ALLA LETTURA')
                self.operator_person.set('Passa il primo indumento')
                self.scan_detail.set('La casella apparirà automaticamente, senza tasto di conferma.')
                self.set_operator_mode('idle')
            self.render_operator_grid(data['slots'],capacity)
            self.operator_note.set('COLLAUDO · antenna da verificare sul PC · stampa diretta Zebra non attiva')
        elif data['reads'] and not self.outbox.pending():
            last=data['reads'][0]
            self.instruction.set(OUTCOMES.get(last['outcome'],last['outcome']).upper())
        self.status.set(('Armadio pieno: prepara la chiusura.' if capacity and occupied==capacity else 'Collegato al gestionale · sessione '+self.session['status'])+' · COLLAUDO')

    def page(self,before):
        if not self.session:return
        self.before=before;self.run(lambda:self.api.snapshot(self.session['id'],before),self.display)

    def older(self):
        if self.snapshot and self.snapshot['reads']:self.page(self.snapshot['reads'][-1]['seq'])

    def close_session(self):
        if self.kind=='pulito' and self.live_reader and self.live_reader.running:
            self.stop_live_reader()
            self.drain_reader_events()
        if not self.session or not self.snapshot:return
        if self.outbox.pending():self.status.set('Letture ancora in verifica. Attendi la conferma e premi di nuovo Chiudi armadio.');return
        if self.kind=='pulito' and not self.placed.get():self.status.set('Conferma che tutti i capi accettati siano nelle caselle indicate.');return
        session=self.session['id'];expected=self.snapshot['counts']['accepted'];note=self.note.get()
        def work():
            self.api.rpc('rf_close_session',p_session=session,p_expected=expected,p_note=note)
            return self.api.snapshot(session)
        def done(data):
            self.display(data)
            if self.kind=='pulito' and data['session']['status']=='chiusa':
                self.show_labels()  # Opens a print preview, never asserts a physical print.
        self.run(work,done)

    def show_labels(self):
        if not self.session or self.session['status']!='chiusa':self.status.set('Le etichette vengono preparate solo dopo la chiusura.');return
        session=str(uuid.UUID(self.session['id']))
        def show(jobs):
            folder=self.directory/'labels';folder.mkdir(exist_ok=True)
            path=folder/(session+'.html');path.write_text(render_labels(jobs),encoding='utf-8')
            webbrowser.open(path.as_uri())
            self.status.set('Anteprima etichette aperta. La stampa fisica non è stata confermata dal programma.')
        self.run(lambda:self.api.labels(session),show)

    def diagnostics(self):
        self.status.set('Rilevazione locale in sola lettura…')
        def show(report):
            window=tk.Toplevel(self.root);window.title('Lettori e stampanti · report locale');window.geometry('850x650')
            ttk.Label(window,text='Report locale: controllalo prima di salvarlo. Non è stato inviato online.',wraplength=800).pack(padx=16,pady=15)
            text=tk.Text(window,wrap='word');text.pack(fill='both',expand=True,padx=16,pady=8)
            text.insert('1.0',json.dumps(report,ensure_ascii=False,indent=2));text.configure(state='disabled')
            def save():
                from tkinter import filedialog
                target=filedialog.asksaveasfilename(parent=window,title='Salva report dispositivi',defaultextension='.json',initialfile='dispositivi-lavanderia.json',filetypes=[('Report JSON','*.json')])
                if target:Path(target).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            ttk.Button(window,text='Salva report sul PC',command=save).pack(pady=12)
            self.status.set('Rilevazione completata. Nessun comando è stato inviato ai dispositivi.')
        self.run(collect_diagnostics,show)

    def start_live_reader(self):
        """Connect to configured standalone COM reader. Never sends LED or RFID commands."""
        if self.kind!='pulito' or not self.session or self.session['status']!='aperta':
            self.status.set('Apri prima una sessione di collaudo dell’armadio.');return
        if self.live_reader and self.live_reader.running:
            self.status.set('Lettura continua già attiva.');return
        if self.outbox.pending():
            self.status.set('Attendi la sincronizzazione delle letture già in coda.');return
        from tkinter import filedialog
        source=filedialog.askopenfilename(parent=self.root,title='Settings.config del lettore RFID',
            filetypes=[('Impostazioni NewPod','*.config'),('Tutti i file','*.*')])
        if not source:return
        try:profile=profile_from_settings(source)
        except (OSError,ProbeError) as error:self.status.set(str(error));return
        self.live_reader=LiveSerialReader(profile,self.reader_events.put)
        try:self.live_reader.start()
        except ProbeError as error:self.status.set(str(error));return
        self.status.set('Collegamento in corso su '+profile.port+' · sola lettura · LED esclusi.')

    def stop_live_reader(self):
        if self.live_reader:
            self.live_reader.stop()
            self.status.set('Lettura continua arrestata. La sessione resta aperta fino alla chiusura.')

    def drain_reader_events(self):
        received=False
        for _ in range(100):
            try:event=self.reader_events.get_nowait()
            except Empty:break
            if event[0]=='state':
                if event[1]=='error':
                    self.status.set(event[2]);self.operator_error(event[2])
                elif event[1]=='active':self.status.set('Lettore attivo su '+event[2]+' · Nessun comando a COM5/LED.')
                continue
            if event[0]!='tag':continue
            tag,port=event[1],event[2]
            if not self.session or self.session['status']!='aperta' or self.kind!='pulito':
                self.status.set('Lettura scartata: nessuna sessione aperta.')
                continue
            try:
                self.outbox.enqueue(self.session['id'],'pulito',tag,
                    metadata={'source':'tagsys_standalone_serial','port':port,'station_kind':'pulito'})
            except (OSError,ValueError):
                self.status.set('Impossibile salvare la lettura locale. Ferma l’operazione e verifica il PC.')
                self.operator_error('Impossibile salvare la lettura locale: controlla la postazione.')
                self.stop_live_reader()
                continue
            self.last_scanned_tag=tag;self.before=None;received=True
            self.active_slot=None
            if self.snapshot:
                self.render_operator_grid(self.snapshot.get('slots') or [],self.session.get('slot_count') if self.session else 90)
            self.instruction.set('VERIFICA IN CORSO')
            self.hero_overline.set('ATTENDI LA CONFERMA')
            self.operator_person.set('Non riporre ancora il capo')
            self.scan_detail.set('Tag '+tag+' · attesa della casella confermata.')
            self.set_operator_mode('warn')
        if received and not self.busy:self.sync()

    def hardware_probe(self):
        if self.busy:return
        if self.probe_window and self.probe_window.winfo_exists():self.probe_window.lift();return
        from tkinter import filedialog
        source=filedialog.askopenfilename(parent=self.root,title='Seleziona Settings.config di Sort Pulito',filetypes=[('Impostazioni','*.config'),('Tutti i file','*.*')])
        if not source:return
        try:profile=profile_from_settings(source)
        except (ProbeError,OSError) as error:self.status.set(str(error));return
        self.probe_stop=Event();stop=self.probe_stop
        window=tk.Toplevel(self.root);window.title('Prova lettore dell’armadio');window.geometry('760x560')
        self.probe_window=window
        ttk.Label(window,text='Lettore su '+profile.port+' · '+str(profile.baudrate)+' baud · formato '+str(profile.field_length)+' caratteri',font=('Segoe UI',15,'bold')).pack(anchor='w',padx=20,pady=16)
        ttk.Label(window,text='Durante una pausa, chiudi Sort Pulito di NewPod e libera l’antenna. Premi Avvia e passa un solo capo entro 10 secondi. Questa prova legge i dati ricevuti senza creare movimenti, accendere LED o stampare.',wraplength=710).pack(anchor='w',padx=20,pady=8)
        output=tk.Text(window,height=14,wrap='word');output.pack(fill='both',expand=True,padx=20,pady=10);output.configure(state='disabled')
        controls=ttk.Frame(window);controls.pack(fill='x',padx=20,pady=12)
        result_saved={}
        def show(result):
            if not window.winfo_exists():return
            result_saved.clear();result_saved.update(result)
            start.configure(state='normal');output.configure(state='normal');output.delete('1.0','end')
            message={'ricevuto':'Codice ricevuto dal lettore. Da confrontare con il capo prima di abilitare la lettura automatica.','formato_da_verificare':'Sono arrivati dati con un formato diverso da quello configurato. Salva il risultato per la verifica.','nessun_codice_completo':'Non è arrivato un codice completo: salva il risultato della prova.','annullata':'Prova interrotta.','errore':'La porta non è disponibile per la prova.'}.get(result.get('status'),'Risultato della prova')
            output.insert('1.0',message+'\n\n'+json.dumps(result,ensure_ascii=False,indent=2));output.configure(state='disabled')
            self.status.set(message)
        def begin():
            if self.busy:return
            stop.clear();start.configure(state='disabled');self.status.set('In ascolto su '+profile.port+' per 10 secondi: passa un solo capo.')
            def work():
                try:return probe_reader(profile,cancelled=stop.is_set)
                except ProbeError as error:return {'status':'errore','message':str(error),'port':profile.port}
            self.run(work,show)
        def save():
            if not result_saved:return
            target=filedialog.asksaveasfilename(parent=window,title='Salva prova lettore',defaultextension='.json',initialfile='prova-lettore-armadio.json',filetypes=[('Report JSON','*.json')])
            if target:Path(target).write_text(json.dumps(result_saved,ensure_ascii=False,indent=2),encoding='utf-8')
        def close():stop.set();window.destroy();self.probe_window=None
        start=ttk.Button(controls,text='Avvia prova di lettura',command=begin);start.pack(side='left')
        ttk.Button(controls,text='Interrompi',command=stop.set).pack(side='left',padx=8)
        ttk.Button(controls,text='Salva risultato sul PC',command=save).pack(side='right')
        window.protocol('WM_DELETE_WINDOW',close)

    def install(self):
        try:
            target=startup.install(self.kind);self.status.set('Installato: '+str(target)+' · avvio automatico al prossimo accesso Windows.')
        except Exception as error:self.status.set(str(error))

    def poll(self):
        if self.stopped:return
        self.drain_reader_events()
        if self.api.token and not self.busy and self.session and self.session['status']=='aperta' and self.before is None:
            if self.outbox.pending() or time.monotonic()>=self.next_refresh_at:
                self.next_refresh_at=time.monotonic()+2.5
                self.sync()
        self.later(100,self.poll)

    def shutdown(self):
        if self.probe_stop:self.probe_stop.set()
        if self.live_reader:self.live_reader.stop()
        self.stopped=True
        for handle in self.after_jobs:self.root.after_cancel(handle)
        self.after_jobs.clear()
        self.pool.shutdown(wait=False,cancel_futures=True);self.root.destroy()


def self_test(kind):
    config=backend_config()
    if getattr(sys,'frozen',False) and not serial_available():raise RuntimeError('Serial transport missing from executable')
    with tempfile.TemporaryDirectory() as directory:
        queue=ReadOutbox(Path(directory)/'test.sqlite3');session=str(uuid.uuid4())
        event=queue.enqueue(session,kind,'0000000000000001')
        queue.sync_once(lambda sid,events:[{'id':event,'outcome':'accettata'}])
        if queue.pending()!=0:raise RuntimeError('Queue acknowledgement failed')
    if os.name=='nt':
        value=b'fixture-token-not-a-credential'
        if _crypt(_crypt(value,True),False)!=value:raise RuntimeError('Windows DPAPI test failed')
        diagnostic=collect_diagnostics()
        if diagnostic.get('read_only') is not True:raise RuntimeError('Windows diagnostic test failed')
    return {'kind':kind,'backend_host':config['url'].split('//')[1],'queue':'ok','dpapi':'ok' if os.name=='nt' else 'windows-only','hardware_connected':False,'mode':'collaudo','gui_toolkit':'ok' if tk is not None else 'unavailable','tcl_version':tk.Tcl().eval('info patchlevel') if tk is not None else None,'diagnostics':'ok' if os.name=='nt' else 'windows-only','serial_transport':'ok' if serial_available() else 'unavailable'}


def main(kind):
    parser=argparse.ArgumentParser()
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--report')
    parser.add_argument('--disable-startup',action='store_true');args=parser.parse_args()
    if args.self_test:
        try:result=self_test(kind)
        except Exception as error:
            if args.report:Path(args.report).write_text(json.dumps({'kind':kind,'error_type':type(error).__name__,'error':str(error)}),encoding='utf-8')
            raise
        if args.report:Path(args.report).write_text(json.dumps(result),encoding='utf-8')
        elif sys.stdout:print(json.dumps(result))
        return
    if args.disable_startup:startup.disable(kind);return
    if tk is None:raise RuntimeError('Libreria grafica non disponibile in questa installazione.')
    root=tk.Tk();directory=data_directory(kind)
    try:lock=InstanceLock(directory/'application.lock')
    except RuntimeError as error:root.withdraw();messagebox.showinfo('Gestore Lavanderia',str(error));root.destroy();return
    try:StationApp(kind,root,directory);root.mainloop()
    except Exception as error:messagebox.showerror('Gestore Lavanderia',str(error));root.destroy()
    finally:lock.close()
