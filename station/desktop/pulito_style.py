"""Native rendering of the Pulito browser design, with no hardware dependencies."""
import tkinter as tk

PAGE = '#f0f3f5'
INK = '#162a35'
MUTED = '#647884'
BORDER = '#dde6eb'
PRIMARY = '#0b7568'
HERO = {'idle': '#173e48', 'ok': '#006d61', 'warn': '#9a6415',
        'bad': '#a61f2b', 'closed': '#34536a'}
SLOT = {'free': ('#ffffff', '#9caeb7', '#dbe5e8'),
        'used': ('#cbefe7', '#096b60', '#8fd9c7'),
        'active': ('#087c70', '#ffffff', '#087c70')}


def background(widget):
    try:return widget.cget('background')
    except tk.TclError:
        from tkinter import ttk
        return ttk.Style(widget).lookup(widget.cget('style') or 'TFrame','background') or PAGE


def rounded(canvas, x1, y1, x2, y2, radius, **options):
    radius = max(0, min(radius, (x2-x1)/2, (y2-y1)/2))
    return canvas.create_polygon(
        x1+radius,y1,x2-radius,y1,x2,y1,x2,y1+radius,
        x2,y2-radius,x2,y2,x2-radius,y2,x1+radius,y2,
        x1,y2,x1,y2-radius,x1,y1+radius,x1,y1,
        smooth=True, splinesteps=24, **options)


class Panel(tk.Canvas):
    """Rounded card containing regular Tk children; resize without recreating them."""
    def __init__(self, master, fill='white', border=BORDER, padding=18, radius=19, **kw):
        super().__init__(master, bg=background(master), bd=0,
                         highlightthickness=0, **kw)
        self.fill, self.border, self.padding, self.radius = fill, border, padding, radius
        self.content = tk.Frame(self, bg=fill)
        self.shape = rounded(self, 1, 1, 2, 2, radius, fill=fill, outline=border)
        self.window = self.create_window(padding, padding, window=self.content, anchor='nw')
        self.bind('<Configure>', self._layout)

    def _layout(self, event=None):
        width, height = self.winfo_width(), self.winfo_height()
        self.delete(self.shape)
        self.shape = rounded(self, 1, 1, width-1, height-1, self.radius,
                             fill=self.fill, outline=self.border)
        self.tag_lower(self.shape)
        self.itemconfigure(self.window, width=max(1,width-2*self.padding),
                           height=max(1,height-2*self.padding))

    def recolor(self, fill):
        self.fill = self.border = fill
        self.content.configure(bg=fill)
        self.itemconfigure(self.shape, fill=fill, outline=fill)


class Button(tk.Canvas):
    """Browser-shaped button with mouse and keyboard activation."""
    def __init__(self, master, text, command, primary=False, width=130, **kw):
        super().__init__(master, width=width, height=44, bd=0, highlightthickness=0,
                         bg=background(master), takefocus=True, cursor='hand2', **kw)
        self.text, self.command, self.primary = text, command, primary
        self.hover = self.focused = False
        self.bind('<Configure>', self._paint)
        self.bind('<Enter>', lambda _:self._highlight(True))
        self.bind('<Leave>', lambda _:self._highlight(False))
        self.bind('<FocusIn>', lambda _:self._focus(True))
        self.bind('<FocusOut>', lambda _:self._focus(False))
        self.bind('<ButtonRelease-1>', lambda _:self.command())
        self.bind('<Return>', lambda _:self.command())
        self.bind('<space>', lambda _:self.command())

    def _highlight(self, value):
        self.hover = value
        self._paint()

    def _focus(self, value):
        self.focused = value
        self._paint()

    def _paint(self, event=None):
        self.delete('all')
        width, height = self.winfo_width(), self.winfo_height()
        fill = ('#096357' if self.hover else PRIMARY) if self.primary else ('#f8fafb' if self.hover else 'white')
        rounded(self, 2, 2, width-2, height-2, 10, fill=fill,
                outline='#66cabb' if self.focused else (PRIMARY if self.primary else '#cfdae0'),
                width=2 if self.focused else 1)
        self.create_text(width/2,height/2,text=self.text,
                         fill='white' if self.primary else '#315463',font=('Segoe UI',-14,'bold'))


class Slot(tk.Canvas):
    """Persistent rounded cabinet tile, matching the web free/used/active states."""
    def __init__(self, master, text, state='free'):
        self.text, self.state = text, state
        self.fill, self.foreground, self.border = SLOT[state]
        super().__init__(master, width=35, height=35, bd=0, highlightthickness=0,
                         bg=background(master), takefocus=False)
        self.bind('<Configure>', self._paint)

    def set_state(self, text, state):
        self.text, self.state = text, state
        self.fill, self.foreground, self.border = SLOT[state]
        self._paint()

    def cget(self, key):
        if key in ('bg','background'):return self.fill
        if key in ('fg','foreground'):return self.foreground
        return super().cget(key)

    def _paint(self, event=None):
        self.delete('all')
        width, height = self.winfo_width(), self.winfo_height()
        if width<5 or height<5:return
        if self.state=='active':
            rounded(self, 0, 0, width, height, 10, fill='#c0eee4', outline='')
        inset=3 if self.state=='active' else 1
        rounded(self,inset,inset,width-inset,height-inset,7,fill=self.fill,outline=self.border)
        self.create_text(width/2,height/2,text=self.text,fill=self.foreground,
                         font=('Segoe UI',-min(24,max(16,int(height*.46))),'bold'))


def configure_theme(root):
    from tkinter import ttk
    root.configure(bg=PAGE)
    root.option_add('*Font',('Segoe UI',-14))
    style=ttk.Style(root)
    style.configure('TFrame',background=PAGE)
    style.configure('TLabel',background=PAGE,foreground=INK,font=('Segoe UI',-14))
    style.configure('Title.TLabel',font=('Segoe UI',-24,'bold'))
    style.configure('Status.TLabel',font=('Segoe UI',-13),foreground=MUTED)
    style.configure('TButton',font=('Segoe UI',-14,'bold'),padding=(14,11),
                    background='white',foreground='#315463',bordercolor='#cfdae0',
                    lightcolor='white',darkcolor='white',focuscolor='#66cabb',relief='flat')
    style.map('TButton',background=[('active','#f8fafb')],foreground=[('disabled','#9caeb7')])
    style.configure('TEntry',font=('Segoe UI',-15),padding=12,fieldbackground='#f8fafb',
                    foreground=INK,bordercolor='#cfdae0',lightcolor='#cfdae0',darkcolor='#cfdae0')
    style.map('TEntry',bordercolor=[('focus','#66cabb')])
    style.configure('TCombobox',padding=9,fieldbackground='white',background='white',
                    foreground=INK,bordercolor='#cfdae0',arrowsize=14)
    style.map('TCombobox',fieldbackground=[('readonly','white')],selectbackground=[('readonly','white')],selectforeground=[('readonly',INK)])
    style.configure('TCheckbutton',background=PAGE,foreground=INK,font=('Segoe UI',-14))
    style.configure('Card.TCheckbutton',background='white')
    style.map('Card.TCheckbutton',background=[('active','white')])
    style.configure('Treeview',font=('Segoe UI',-14),rowheight=34,fieldbackground='white',background='white',foreground=INK,bordercolor=BORDER)
    style.configure('Treeview.Heading',font=('Segoe UI',-13,'bold'),background='#f8fafb',foreground='#405d69',padding=10)


def brand(parent, context, menu=None):
    header=tk.Frame(parent,bg=PAGE)
    header.pack(fill='x',pady=(0,12))
    mark=Panel(header,fill='#153f4b',border='#153f4b',padding=8,radius=15,width=47,height=47)
    mark.pack(side='left',padx=(0,12))
    tk.Label(mark.content,text='GL',font=('Segoe UI',-21,'bold'),bg='#153f4b',fg='white').place(relx=.5,rely=.5,anchor='center')
    title=tk.Frame(header,bg=PAGE)
    title.pack(side='left',fill='x',expand=True)
    tk.Label(title,text='PULITO · ARMADIO',font=('Segoe UI',-19,'bold'),bg=PAGE,fg=INK).pack(anchor='w')
    tk.Label(title,textvariable=context,font=('Segoe UI',-13),bg=PAGE,fg=MUTED).pack(anchor='w',pady=(2,0))
    if menu:Button(header,text='☰  Menu',command=menu,width=108).pack(side='right')
    return header
