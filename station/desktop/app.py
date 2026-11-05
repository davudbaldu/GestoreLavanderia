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
from .config import backend_config, data_directory, Preferences
from .credentials import TokenStore, _crypt
from .cloud import CloudAPI, CloudError
from . import startup
from .labels import render_labels
from .diagnostics import collect as collect_diagnostics
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
        self.session=None; self.snapshot=None; self.before=None; self.remember=False; self.labels=[]
        self.root.title(('Sporco' if kind=='sporco' else 'Pulito')+' · Gestore Lavanderia · COLLAUDO')
        self.root.geometry('1180x860'); self.root.minsize(920,680); self.root.configure(bg='#f3f6fb')
        style=ttk.Style(); style.theme_use('clam')
        style.configure('TFrame',background='#f3f6fb');style.configure('TLabel',background='#f3f6fb',foreground='#213750',font=('Segoe UI',10))
        style.configure('Title.TLabel',font=('Segoe UI',24,'bold'));style.configure('Status.TLabel',font=('Segoe UI',11))
        style.configure('TButton',font=('Segoe UI',10),padding=9);style.configure('TEntry',padding=7)
        self.status=tk.StringVar(value='Accedi al gestionale per collegare questa postazione.')
        ttk.Label(root,text='GESTORE LAVANDERIA · '+kind.upper(),style='Title.TLabel').pack(anchor='w',padx=24,pady=(20,6))
        ttk.Label(root,text='COLLAUDO SOFTWARE · antenne e stampanti non ancora collegate',foreground='#966416').pack(anchor='w',padx=24)
        self.body=ttk.Frame(root);self.body.pack(fill='both',expand=True,padx=24,pady=18)
        ttk.Label(root,textvariable=self.status,style='Status.TLabel',wraplength=1120).pack(fill='x',padx=24,pady=(0,18))
        self.show_login();self.root.protocol('WM_DELETE_WINDOW',self.shutdown)
        if self.store.path.exists():
            self.run(self.restore,self.show_station)
        self.root.after(3000,self.poll)

    def run(self, work, done):
        if self.busy or self.stopped:return
        self.busy=True
        future=self.pool.submit(work)
        def check():
            if self.stopped:return
            if not future.done():self.root.after(80,check);return
            self.busy=False
            try:
                value=future.result()
                if self.remember and self.api.refresh_token:
                    self.store.save(self.api.refresh_token)
                done(value)
            except Exception as error:
                self.status.set(str(error))
        self.root.after(80,check)

    def restore(self):
        self.api.refresh(self.store.load());self.remember=True
        return self.api.lists()

    def clear_body(self):
        for child in self.body.winfo_children():child.destroy()

    def show_login(self):
        self.clear_body();frame=ttk.Frame(self.body);frame.pack(anchor='n',pady=45)
        ttk.Label(frame,text='Collega il gestionale online',font=('Segoe UI',17,'bold')).pack(anchor='w',pady=12)
        ttk.Label(frame,text='Email').pack(anchor='w');email=ttk.Entry(frame,width=48);email.pack(pady=(4,15))
        ttk.Label(frame,text='Password').pack(anchor='w');password=ttk.Entry(frame,show='•',width=48);password.pack(pady=(4,15))
        remember=tk.BooleanVar(value=False)
        ttk.Checkbutton(frame,text='Ricorda la sessione, protetta per questo utente Windows',variable=remember,state='normal' if os.name=='nt' else 'disabled').pack(anchor='w',pady=10)
        def login():
            mail=email.get().strip();secret=password.get();password.delete(0,'end');self.remember=remember.get()
            self.status.set('Collegamento in corso…')
            def work():
                self.api.login(mail,secret)
                if not self.remember:self.store.clear()
                return self.api.lists()
            self.run(work,self.show_station)
        ttk.Button(frame,text='Accedi',command=login).pack(anchor='w',pady=10)
        password.bind('<Return>',lambda _:login())
        ttk.Button(frame,text='Rileva lettori e stampanti',command=self.diagnostics).pack(anchor='w',pady=14)

    def show_station(self, data):
        stations,self.clients,self.open_sessions=data;self.stations=[s for s in stations if s['kind']==self.kind]
        if not self.stations or not self.clients:raise CloudError('Nessuna postazione o struttura configurata.')
        self.clear_body();top=ttk.Frame(self.body);top.pack(fill='x')
        names=[s['name'] for s in self.stations]
        self.station_choice=ttk.Combobox(top,values=names,state='readonly',width=22);self.station_choice.pack(side='left',padx=(0,12))
        previous=self.preferences.data.get('station_id');self.station_choice.current(next((i for i,s in enumerate(self.stations) if s['id']==previous),0))
        self.client_choice=ttk.Combobox(top,values=[c['name']+' · '+c['site'] for c in self.clients],state='readonly',width=32);self.client_choice.current(0);self.client_choice.pack(side='left',padx=(0,12))
        self.archive_choice=ttk.Combobox(top,values=['Tutti i capi della struttura','Ospiti · capi personali','Operatori · divise'],state='readonly',width=26);self.archive_choice.current(0);self.archive_choice.pack(side='left')
        self.empty=tk.BooleanVar(value=False)
        if self.kind=='pulito':ttk.Checkbutton(self.body,text='Confermo che tutte le caselle sono state svuotate prima di iniziare.',variable=self.empty).pack(anchor='w',pady=(16,2))
        controls=ttk.Frame(self.body);controls.pack(fill='x',pady=12)
        ttk.Button(controls,text='Apri sessione di collaudo',command=self.start).pack(side='left')
        ttk.Button(controls,text='Riprendi sessione aperta',command=self.resume).pack(side='left',padx=10)
        ttk.Button(controls,text='Rileva dispositivi',command=self.diagnostics).pack(side='left',padx=10)
        ttk.Button(controls,text='Installa su questo PC e avvia con Windows',command=self.install).pack(side='right')
        self.context=tk.StringVar(value='Scegli struttura e postazione. L’identità della postazione rimane memorizzata su questo PC.')
        ttk.Label(self.body,textvariable=self.context,wraplength=1100).pack(anchor='w',pady=8)
        scan=ttk.Frame(self.body);scan.pack(fill='x',pady=8)
        ttk.Label(scan,text='Tag di prova (uno alla volta sul pulito; separati da spazi o righe sullo sporco)').pack(anchor='w')
        self.tag_input=ttk.Entry(scan);self.tag_input.pack(side='left',fill='x',expand=True,pady=8)
        ttk.Button(scan,text='Invia prova',command=self.capture).pack(side='right',padx=(12,0));self.tag_input.bind('<Return>',lambda _:self.capture())
        self.instruction=tk.StringVar(value='In attesa di una lettura confermata dal server.')
        ttk.Label(self.body,textvariable=self.instruction,font=('Segoe UI',22,'bold'),wraplength=1080).pack(anchor='w',pady=10)
        self.counts=tk.StringVar(value='');ttk.Label(self.body,textvariable=self.counts).pack(anchor='w',pady=4)
        self.grid=ttk.Frame(self.body);self.grid.pack(fill='x',pady=8)
        log=ttk.Frame(self.body);log.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(log,columns=('tag','name','outcome','slot'),show='headings',height=7)
        for name,width in [('tag',225),('name',270),('outcome',255),('slot',80)]:self.tree.heading(name,text={'tag':'Tag','name':'Nominativo','outcome':'Esito','slot':'Casella'}[name]);self.tree.column(name,width=width,minwidth=65)
        scrollbar=ttk.Scrollbar(log,orient='vertical',command=self.tree.yview);self.tree.configure(yscrollcommand=scrollbar.set);scrollbar.pack(side='right',fill='y');self.tree.pack(fill='both',expand=True)
        pages=ttk.Frame(self.body);pages.pack(fill='x',pady=8)
        ttk.Button(pages,text='Più recenti',command=lambda:self.page(None)).pack(side='left');ttk.Button(pages,text='Precedenti',command=self.older).pack(side='left',padx=10)
        ttk.Button(pages,text='Etichette della sessione',command=self.show_labels).pack(side='right')
        self.note=ttk.Entry(self.body);self.note.pack(fill='x',pady=4);self.note.insert(0,'')
        ttk.Label(self.body,text='Nota di chiusura: obbligatoria se ci sono capi segnalati da separare.').pack(anchor='w')
        self.placed=tk.BooleanVar(value=False)
        if self.kind=='pulito':ttk.Checkbutton(self.body,text='Confermo che i capi accettati sono nelle caselle indicate.',variable=self.placed).pack(anchor='w',pady=6)
        ttk.Button(self.body,text='Chiudi armadio e prepara etichette' if self.kind=='pulito' else 'Termina sessione sporco',command=self.close_session).pack(anchor='w',pady=6)
        self.status.set('Collegato al gestionale. Modalità collaudo: nessuna lettura proviene ancora dall’antenna.')

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
        self.tag_input.delete(0,'end');self.before=None;self.instruction.set('In attesa di conferma — non assegnare ancora il capo.' if self.kind=='pulito' else 'Letture salvate localmente; invio al gestionale…')
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
        for read in data['reads']:self.tree.insert('', 'end', values=(read['tag'],read['snapshot'].get('name','—'),OUTCOMES.get(read['outcome'],read['outcome']),read['slot'] or '—'))
        for child in self.grid.winfo_children():child.destroy()
        if self.kind=='pulito':
            for index in range(capacity):
                slot=next((s for s in data['slots'] if s['slot']==index+1),None)
                label=tk.Label(self.grid,text=str(index+1).zfill(2)+(f" · {slot['count']}" if slot else ''),bg='#b6f0d5' if slot else '#e4eaf2',fg='#173b3a',font=('Segoe UI',9),padx=4,pady=3)
                label.grid(row=index//15,column=index%15,sticky='ew',padx=2,pady=2)
            for column in range(15):self.grid.columnconfigure(column,weight=1)
        if data['reads'] and not self.outbox.pending():
            last=data['reads'][0]
            self.instruction.set(('CASELLA '+str(last['slot'])+' · '+last['snapshot'].get('name','')) if self.kind=='pulito' and last['slot'] else OUTCOMES.get(last['outcome'],last['outcome']).upper())
        self.status.set(('Armadio pieno: prepara la chiusura.' if capacity and occupied==capacity else 'Collegato al gestionale · sessione '+self.session['status'])+' · COLLAUDO')

    def page(self,before):
        if not self.session:return
        self.before=before;self.run(lambda:self.api.snapshot(self.session['id'],before),self.display)

    def older(self):
        if self.snapshot and self.snapshot['reads']:self.page(self.snapshot['reads'][-1]['seq'])

    def close_session(self):
        if not self.session or not self.snapshot:return
        if self.outbox.pending():self.status.set('Prima di chiudere, invia tutte le letture in attesa.');return
        if self.kind=='pulito' and not self.placed.get():self.status.set('Conferma che tutti i capi accettati siano nelle caselle indicate.');return
        session=self.session['id'];expected=self.snapshot['counts']['accepted'];note=self.note.get()
        def work():
            self.api.rpc('rf_close_session',p_session=session,p_expected=expected,p_note=note)
            return self.api.snapshot(session)
        self.run(work,self.display)

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

    def install(self):
        try:
            target=startup.install(self.kind);self.status.set('Installato: '+str(target)+' · avvio automatico al prossimo accesso Windows.')
        except Exception as error:self.status.set(str(error))

    def poll(self):
        if self.stopped:return
        if self.api.token and not self.busy and self.session and self.session['status']=='aperta' and self.before is None:self.sync()
        self.root.after(3000,self.poll)

    def shutdown(self):
        self.stopped=True;self.pool.shutdown(wait=False,cancel_futures=True);self.root.destroy()


def self_test(kind):
    config=backend_config()
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
    return {'kind':kind,'backend_host':config['url'].split('//')[1],'queue':'ok','dpapi':'ok' if os.name=='nt' else 'windows-only','hardware_connected':False,'mode':'collaudo','gui_toolkit':'ok' if tk is not None else 'unavailable','tcl_version':tk.Tcl().eval('info patchlevel') if tk is not None else None,'diagnostics':'ok' if os.name=='nt' else 'windows-only'}


def main(kind):
    parser=argparse.ArgumentParser()
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--report')
    parser.add_argument('--disable-startup',action='store_true');args=parser.parse_args()
    if args.self_test:
        result=self_test(kind)
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
