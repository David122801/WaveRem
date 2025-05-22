import os
import subprocess
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk
import threading
import time

# --- Variables Globales para Widgets Tkinter (para permitir el acceso desde varias funciones) ---
entry_file_path = None
label_duration = None
entry_start_time = None
entry_end_time = None
entry_output_name = None
status_label = None
output_format_combobox = None
waveform_canvas = None
waveform_start_line = None
waveform_end_line = None
waveform_selection_rect = None
waveform_drag_start_x = None
waveform_current_file_duration = 0

# Nuevas variables globales para la guía de tiempos y etiquetas de selección
time_ruler_canvas = None
selected_start_time_label = None
selected_end_time_label = None

# --- Funciones Auxiliares ---

def time_to_seconds(time_str):
    """Convierte un tiempo en formato hh:mm:ss a segundos."""
    try:
        hours, minutes, seconds = map(int, time_str.split(':'))
        return hours * 3600 + minutes * 60 + seconds
    except ValueError:
        # Maneja casos donde los segundos pueden tener milisegundos (ej. de la salida de ffprobe)
        if '.' in time_str:
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        raise ValueError("El formato del tiempo debe ser hh:mm:ss o hh:mm:ss.ms")

def format_seconds_to_time(seconds):
    """Convierte segundos a formato hh:mm:ss."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"

def get_media_duration(file_path):
    """Obtiene la duración de un archivo de video o audio usando ffprobe."""
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        duration = float(result.stdout.strip())
        return duration # Retorna en segundos para cálculos más precisos
    except Exception as e:
        print(f"Error al obtener la duración del medio: {e}")
        return 0.0

def center_window(master, width, height):
    """Centra la ventana en la pantalla."""
    master.geometry(f"{width}x{height}")
    screen_width = master.winfo_screenwidth()
    screen_height = master.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    master.geometry(f"{width}x{height}+{x}+{y}")

# --- Visualización de Onda (Simulada) y Guía de Tiempos ---

def draw_time_ruler(canvas, duration_seconds):
    """Dibuja una guía de tiempos en el canvas del ruler."""
    canvas.delete("all") # Limpia el ruler anterior
    width = canvas.winfo_width()
    height = canvas.winfo_height()

    if width == 1 or height == 1 or duration_seconds == 0:
        return

    # Determina el intervalo de las marcas de tiempo
    if duration_seconds < 30:
        interval = 5 # Cada 5 segundos
    elif duration_seconds < 120:
        interval = 10 # Cada 10 segundos
    elif duration_seconds < 600:
        interval = 30 # Cada 30 segundos (0.5 minutos)
    else:
        interval = 60 # Cada 60 segundos (1 minuto)

    for sec in range(0, int(duration_seconds) + 1, interval):
        x_pos = (sec / duration_seconds) * width
        
        # Dibujar línea más larga para el intervalo principal
        canvas.create_line(x_pos, 0, x_pos, height, fill="gray", width=1, tags="ruler_marks")
        canvas.create_text(x_pos, height / 2, text=format_seconds_to_time(sec), 
                           fill="white", font=('Inter', 8), anchor="n", tags="ruler_text")
    
    # Dibujar marcas intermedias si el intervalo principal es grande
    if interval > 10:
        for sec in range(0, int(duration_seconds) + 1, interval // 2):
            if sec % interval != 0: # No dibujar si ya es una marca principal
                x_pos = (sec / duration_seconds) * width
                canvas.create_line(x_pos, height * 0.75, x_pos, height, fill="darkgray", width=1, tags="ruler_marks")


def draw_simulated_waveform(canvas, duration_seconds):
    """Dibuja una forma de onda simulada en el canvas."""
    canvas.delete("waveform_lines") # Limpia las líneas de la forma de onda anterior
    width = canvas.winfo_width()
    height = canvas.winfo_height()
    
    if width == 1 or height == 1 or duration_seconds == 0: # Canvas podría no estar completamente renderizado o duración cero
        return

    # Dibuja un patrón de forma de onda simple y genérico
    line_color = "#4CAF50" # Color verdoso
    num_peaks = 100 # Más picos para una apariencia más densa
    peak_height = height * 0.4
    base_y = height / 2

    # Generar puntos de la forma de onda
    points = []
    for i in range(num_peaks):
        x = i * (width / (num_peaks - 1))
        # Simula una amplitud variable con una función seno para suavidad
        amplitude_factor = (1 + (i % 2 - 0.5) * 0.5) * (0.5 + 0.5 * abs(0.5 - (i / num_peaks))) # Variación más compleja
        y_top = base_y - peak_height * amplitude_factor
        y_bottom = base_y + peak_height * amplitude_factor
        
        points.append((x, y_top))
        points.append((x, y_bottom))

    # Conecta los puntos para formar una forma similar a una onda
    for i in range(len(points) - 1):
        canvas.create_line(points[i][0], points[i][1], points[i+1][0], points[i+1][1], 
                           fill=line_color, width=2, tags="waveform_lines")

    # Dibuja una línea horizontal para el centro
    canvas.create_line(0, base_y, width, base_y, fill="#66BB6A", width=1, tags="waveform_lines")

    # Inicializa o actualiza las líneas de selección y el rectángulo
    global waveform_start_line, waveform_end_line, waveform_selection_rect
    if waveform_start_line is None:
        waveform_start_line = canvas.create_line(0, 0, 0, height, fill="red", width=2, tags="selection_elements")
        waveform_end_line = canvas.create_line(width, 0, width, height, fill="blue", width=2, tags="selection_elements")
        waveform_selection_rect = canvas.create_rectangle(0, 0, width, height, outline="", fill="#FFFFFF33", tags="selection_elements") # Semi-transparente
    else:
        # Asegura que las líneas y el rectángulo de selección existan y se actualicen
        canvas.coords(waveform_start_line, 0, 0, 0, height)
        canvas.coords(waveform_end_line, width, 0, width, height)
        canvas.coords(waveform_selection_rect, 0, 0, width, height)
        canvas.tag_raise("selection_elements") # Asegura que las líneas de selección estén encima

    update_waveform_selection_lines(0, duration_seconds)


def on_waveform_press(event):
    """Maneja el evento de presionar el botón del mouse en la forma de onda."""
    global waveform_drag_start_x
    waveform_drag_start_x = event.x
    # Reinicia la selección al presionar de nuevo
    canvas_width = waveform_canvas.winfo_width()
    waveform_canvas.coords(waveform_selection_rect, event.x, 0, event.x, waveform_canvas.winfo_height())
    waveform_canvas.coords(waveform_start_line, event.x, 0, event.x, waveform_canvas.winfo_height())
    waveform_canvas.coords(waveform_end_line, event.x, 0, event.x, waveform_canvas.winfo_height())


def on_waveform_drag(event):
    """Maneja el evento de arrastrar el mouse en la forma de onda."""
    if waveform_drag_start_x is not None:
        x1 = min(waveform_drag_start_x, event.x)
        x2 = max(waveform_drag_start_x, event.x)
        waveform_canvas.coords(waveform_selection_rect, x1, 0, x2, waveform_canvas.winfo_height())
        waveform_canvas.coords(waveform_start_line, x1, 0, x1, waveform_canvas.winfo_height())
        waveform_canvas.coords(waveform_end_line, x2, 0, x2, waveform_canvas.winfo_height())

def on_waveform_release(event):
    """Maneja el evento de soltar el botón del mouse en la forma de onda."""
    global waveform_drag_start_x
    if waveform_drag_start_x is not None:
        x1_pixel = min(waveform_drag_start_x, event.x)
        x2_pixel = max(waveform_drag_start_x, event.x)
        
        canvas_width = waveform_canvas.winfo_width()
        
        if waveform_current_file_duration > 0 and canvas_width > 0:
            start_ratio = x1_pixel / canvas_width
            end_ratio = x2_pixel / canvas_width
            
            start_sec = start_ratio * waveform_current_file_duration
            end_sec = end_ratio * waveform_current_file_duration
            
            entry_start_time.delete(0, tk.END)
            entry_start_time.insert(0, format_seconds_to_time(start_sec))
            
            entry_end_time.delete(0, tk.END)
            entry_end_time.insert(0, format_seconds_to_time(end_sec))
            
            update_waveform_selection_lines(start_sec, end_sec)
            
        waveform_drag_start_x = None

def update_waveform_selection_lines(start_sec, end_sec):
    """Actualiza la posición de las líneas de selección en el canvas y las etiquetas de tiempo."""
    if waveform_canvas and waveform_current_file_duration > 0:
        canvas_width = waveform_canvas.winfo_width()
        canvas_height = waveform_canvas.winfo_height()

        start_x = (start_sec / waveform_current_file_duration) * canvas_width
        end_x = (end_sec / waveform_current_file_duration) * canvas_width

        waveform_canvas.coords(waveform_start_line, start_x, 0, start_x, canvas_height)
        waveform_canvas.coords(waveform_end_line, end_x, 0, end_x, canvas_height)
        waveform_canvas.coords(waveform_selection_rect, start_x, 0, end_x, canvas_height)
        
        # Actualiza las etiquetas de tiempo de selección
        selected_start_time_label.config(text=f"Inicio: {format_seconds_to_time(start_sec)}")
        selected_end_time_label.config(text=f"Fin: {format_seconds_to_time(end_sec)}")

# --- File Selection and Duration ---

def select_file(entry_file_path_widget, label_duration_widget):
    """Abre un diálogo para seleccionar un archivo de video/audio y muestra su duración."""
    file_path = filedialog.askopenfilename(filetypes=[
        ("Archivos de medios", "*.mp4;*.wmv;*.avi;*.mov;*.mkv;*.mp3;*.aac;*.wav;*.flac"),
        ("Todos los archivos", "*.*")
    ])
    if file_path:
        select_file_from_path(file_path, entry_file_path_widget, label_duration_widget)

def select_file_from_path(file_path, entry_file_path_widget, label_duration_widget):
    """Actualiza la interfaz con la ruta del archivo y su duración."""
    entry_file_path_widget.delete(0, tk.END)
    entry_file_path_widget.insert(0, file_path)

    duration_seconds = get_media_duration(file_path)
    label_duration_widget.config(text=f"Duración del medio: {format_seconds_to_time(duration_seconds)}")
    
    global waveform_current_file_duration
    waveform_current_file_duration = duration_seconds
    
    # Dibuja la forma de onda simulada y la guía de tiempos para el nuevo archivo
    draw_simulated_waveform(waveform_canvas, waveform_current_file_duration)
    draw_time_ruler(time_ruler_canvas, waveform_current_file_duration)
    
    # Reinicia los tiempos de inicio/fin
    entry_start_time.delete(0, tk.END)
    entry_start_time.insert(0, "00:00:00")
    entry_end_time.delete(0, tk.END)
    entry_end_time.insert(0, format_seconds_to_time(duration_seconds))
    
    update_waveform_selection_lines(0, waveform_current_file_duration)


# --- Lógica de Corte de Video ---

def start_cut_video_thread():
    """Inicia el proceso de corte de video en un hilo separado."""
    threading.Thread(target=cut_video, daemon=True).start()

def cut_video():
    """Corta el video o audio utilizando FFmpeg."""
    file_path = entry_file_path.get()
    start_time_str = entry_start_time.get()
    end_time_str = entry_end_time.get()
    output_name = entry_output_name.get()
    selected_format = output_format_combobox.get()

    if not file_path or not start_time_str or not end_time_str or not output_name or not selected_format:
        messagebox.showerror("Error", "Por favor, complete todos los campos y seleccione un formato de salida.")
        return

    try:
        start_seconds = time_to_seconds(start_time_str)
        end_seconds = time_to_seconds(end_time_str)
    except ValueError as e:
        messagebox.showerror("Error de formato de tiempo", str(e))
        return

    if end_seconds <= start_seconds:
        messagebox.showerror("Error de tiempo", "El tiempo de fin debe ser mayor que el tiempo de inicio.")
        return

    media_duration_seconds = waveform_current_file_duration # Usamos la duración global ya obtenida

    if end_seconds > media_duration_seconds:
        messagebox.showerror("Error de tiempo", "El tiempo de fin es mayor que la duración total del archivo.")
        return

    # Determina la extensión de salida
    output_extension = "." + selected_format.lower() if not selected_format.startswith('.') else selected_format.lower()

    output_dir = "VideoFinal"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_path = os.path.join(output_dir, f"{output_name}{output_extension}")

    if os.path.exists(output_path):
        messagebox.showerror("Error", f"El archivo '{output_name}{output_extension}' ya existe en la carpeta '{output_dir}'. Elija otro nombre.")
        return

    progress_window = tk.Toplevel()
    progress_window.title("Cortando...")
    progress_window.geometry("300x120")
    progress_window.resizable(False, False)
    center_window(progress_window, 300, 120)

    progress_label = tk.Label(progress_window, text="Iniciando corte...", wraplength=250)
    progress_label.pack(pady=10)

    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
    progress_bar.pack(padx=20, pady=5, fill='x')

    percentage_label = tk.Label(progress_window, text="0%")
    percentage_label.pack()

    status_label.config(text="Procesando...", fg="orange")

    def update_progress(percentage):
        progress_var.set(percentage)
        percentage_label.config(text=f"{percentage:.1f}%")
        progress_window.update_idletasks()

    def run_cutting_process():
        try:
            process_video(file_path, start_seconds, end_seconds, output_path, update_progress)
            progress_window.destroy()
            status_label.config(text=f"Archivo '{output_name}{output_extension}' cortado con éxito", fg="green")
            messagebox.showinfo("Éxito", f"Archivo cortado con éxito: {output_path}")
        except Exception as e:
            progress_window.destroy()
            status_label.config(text="Error al cortar el archivo", fg="red")
            messagebox.showerror("Error", f"No se pudo cortar el archivo: {e}\nAsegúrese de que FFmpeg esté instalado y en su PATH.")

    threading.Thread(target=run_cutting_process, daemon=True).start()


def process_video(input_file, start_sec, end_sec, output_file, progress_callback):
    """Ejecuta el comando FFmpeg para cortar el video/audio."""
    duration_segment = end_sec - start_sec

    # Comando base de FFmpeg
    cmd = [
        'ffmpeg',
        '-ss', str(start_sec),  # Tiempo de inicio
        '-i', input_file,       # Archivo de entrada
        '-t', str(duration_segment) # Duración del segmento a cortar
    ]

    # Determina el formato de salida y aplica los códecs apropiados
    output_extension = os.path.splitext(output_file)[1].lower()

    if output_extension in ['.mp4', '.mov', '.mkv']:
        # Para contenedores de video, intenta copiar los streams si es posible, de lo contrario recodifica
        cmd.extend(['-c:v', 'copy', '-c:a', 'copy'])
    elif output_extension in ['.mp3']:
        cmd.extend(['-vn', '-ab', '192k']) # Sin video, bitrate de audio 192kbps
    elif output_extension in ['.wav']:
        cmd.extend(['-vn', '-acodec', 'pcm_s16le']) # Sin video, PCM 16-bit little-endian
    elif output_extension in ['.aac']:
        cmd.extend(['-vn', '-c:a', 'aac', '-b:a', '128k']) # Sin video, audio AAC
    elif output_extension in ['.flac']:
        cmd.extend(['-vn', '-c:a', 'flac']) # Sin video, audio FLAC
    else:
        # Por defecto, recodifica si el formato es desconocido o requiere conversión
        cmd.extend(['-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-c:a', 'aac', '-b:a', '128k'])
    
    cmd.append(output_file)

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW # Evita que aparezca una ventana de consola en Windows
        )

        for line in process.stderr:
            if 'time=' in line:
                try:
                    time_str = line.split('time=')[1].split()[0]
                    hours, minutes, seconds = map(float, time_str.split(':'))
                    current_processed_time = hours * 3600 + minutes * 60 + seconds
                    
                    if duration_segment > 0:
                        progress = min(100, max(0, (current_processed_time / duration_segment) * 100))
                        progress_callback(progress)
                except Exception as e:
                    print(f"Error de seguimiento de progreso: {e}")

        process.wait()
        if process.returncode != 0:
            error_output = process.stderr.read()
            raise Exception(f"FFmpeg falló con el código {process.returncode}: {error_output}")

    except FileNotFoundError:
        raise Exception("FFmpeg no encontrado. Asegúrese de que esté instalado y en su PATH.")
    except Exception as e:
        raise Exception(f"Error en el proceso FFmpeg: {e}")

    progress_callback(100) # Asegura que se muestre el 100% de completado
    return output_file

# --- Lógica de Previsualización de Video ---

def start_preview_thread():
    """Inicia la previsualización de video en un hilo separado."""
    threading.Thread(target=preview_video, daemon=True).start()

def preview_video():
    """Muestra una previsualización del segmento de video seleccionado."""
    file_path = entry_file_path.get()
    start_time_str = entry_start_time.get()
    end_time_str = entry_end_time.get()

    if not file_path or not start_time_str or not end_time_str:
        messagebox.showerror("Error", "Por favor, complete todos los campos para la previsualización.")
        return

    try:
        start_sec = time_to_seconds(start_time_str)
        end_sec = time_to_seconds(end_time_str)
    except ValueError as e:
        messagebox.showerror("Error de formato de tiempo", str(e))
        return

    if end_sec <= start_sec:
        messagebox.showerror("Error de tiempo", "El tiempo de fin debe ser mayor que el tiempo de inicio para la previsualización.")
        return

    cap = cv2.VideoCapture(file_path)

    if not cap.isOpened():
        messagebox.showerror("Error", "No se pudo abrir el archivo de video. Asegúrese de que es un archivo de video válido.")
        return

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    delay = int(1000 / fps) if fps > 0 else 33 # Por defecto ~30fps

    preview_window = tk.Toplevel()
    preview_window.title("Previsualización")
    preview_window.geometry("800x600")
    center_window(preview_window, 800, 600)

    canvas_preview = tk.Canvas(preview_window, bg="black")
    canvas_preview.pack(fill="both", expand=True)

    controls_frame = tk.Frame(preview_window, bg="#333")
    controls_frame.pack(fill="x", side="bottom", padx=5, pady=5)

    time_label = tk.Label(controls_frame, text=f"{start_time_str} / {end_time_str}", fg="white", bg="#333")
    time_label.pack(side="left", padx=5)

    playing = True
    last_update = time.time()

    def seek_video_preview(event):
        nonlocal current_time_preview
        width = progress_bar_preview.winfo_width()
        if width > 0:
            percentage = event.x / width
            current_time_preview = start_sec + (end_sec - start_sec) * percentage
            cap.set(cv2.CAP_PROP_POS_MSEC, int(current_time_preview * 1000))
            update_frame_preview(True)

    def toggle_play_preview():
        nonlocal playing, last_update
        playing = not playing
        last_update = time.time()
        play_button_preview.config(text="⏸" if playing else "▶")
        if playing:
            update_frame_preview()

    def reset_video_preview():
        nonlocal current_time_preview, playing, last_update
        current_time_preview = start_sec
        cap.set(cv2.CAP_PROP_POS_MSEC, int(start_sec * 1000))
        playing = True
        last_update = time.time()
        play_button_preview.config(text="⏸")
        update_frame_preview(True)

    def update_progress_preview():
        current_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        current_time_preview = current_ms / 1000
        
        # Calcula el progreso relativo al segmento seleccionado
        if (end_sec - start_sec) > 0:
            progress = (current_time_preview - start_sec) / (end_sec - start_sec)
            progress_bar_preview.set(progress)
        else:
            progress_bar_preview.set(0) # Evita la división por cero
        
        time_label.config(text=f"{format_seconds_to_time(current_time_preview)} / {format_seconds_to_time(end_sec)}")

    def update_frame_preview(force=False):
        nonlocal last_update
        
        if not playing and not force:
            preview_window.after(delay, update_frame_preview)
            return

        current = time.time()
        elapsed = current - last_update
        
        if elapsed < delay/1000 and not force:
            preview_window.after(1, update_frame_preview)
            return

        ret, frame = cap.read()
        if ret:
            current_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            if current_ms/1000 >= end_sec:
                reset_video_preview()
                return

            canvas_width = canvas_preview.winfo_width()
            canvas_height = canvas_preview.winfo_height()
            
            # Escalado eficiente
            scale = min(canvas_width/frame.shape[1], canvas_height/frame.shape[0])
            if scale != 1:
                width = int(frame.shape[1] * scale)
                height = int(frame.shape[0] * scale)
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)

            # Conversión de color optimizada
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            photo = ImageTk.PhotoImage(image=img)
            
            # Centrado de la imagen
            x = (canvas_width - width) // 2
            y = (canvas_height - height) // 2
            
            canvas_preview.delete("all")
            canvas_preview.create_image(x, y, anchor="nw", image=photo)
            canvas_preview.image = photo # Mantiene una referencia!

            update_progress_preview()
            last_update = current
            
            if playing:
                preview_window.after(1, update_frame_preview)
        else:
            reset_video_preview()

    progress_var_preview = tk.DoubleVar(value=0)
    progress_bar_preview = ttk.Scale(controls_frame, from_=0, to=1, orient="horizontal",
                                     variable=progress_var_preview)
    progress_bar_preview.pack(side="left", fill="x", expand=True, padx=5)

    play_button_preview = tk.Button(controls_frame, text="⏸", command=toggle_play_preview,
                                    bg="#555", fg="white", font=('TkDefaultFont', 12))
    play_button_preview.pack(side="left", padx=5)

    reset_button_preview = tk.Button(controls_frame, text="⟲", command=reset_video_preview,
                                     bg="#555", fg="white", font=('TkDefaultFont', 12))
    reset_button_preview.pack(side="left", padx=5)

    progress_bar_preview.bind("<Button-1>", seek_video_preview)
    
    cap.set(cv2.CAP_PROP_POS_MSEC, int(start_sec * 1000))
    current_time_preview = start_sec # Inicializa current_time_preview para el ámbito
    update_frame_preview(True)

    def on_closing_preview():
        cap.release()
        preview_window.destroy()

    preview_window.protocol("WM_DELETE_WINDOW", on_closing_preview)

# --- Ventana Principal de la Aplicación ---

def create_video_cutter_window():
    """Crea la ventana principal de la aplicación de corte de video."""
    master = tk.Tk()
    master.title("Cortador de Video/Audio Avanzado")
    center_window(master, 700, 750) # Todavía la centramos inicialmente
    master.resizable(True, True) # Permitimos redimensionar la ventana
    master.configure(bg="#f0f0f0") # Fondo gris claro

    # Estilo
    style = ttk.Style()
    style.theme_use('clam') # 'clam', 'alt', 'default', 'classic'
    style.configure('TLabel', background='#f0f0f0', foreground='#333333', font=('Inter', 10))
    # CORRECCIÓN: Se añadió la comilla doble de cierre en "flat"
    style.configure('TButton', background='#4CAF50', foreground='white', font=('Inter', 10, 'bold'), borderwidth=0, relief="flat")
    style.map('TButton', background=[('active', '#66BB6A')])
    style.configure('TEntry', fieldbackground='white', foreground='#333333', font=('Inter', 10), borderwidth=1, relief="solid")
    style.configure('TCombobox', fieldbackground='white', foreground='#333333', font=('Inter', 10))
    style.configure('Horizontal.TProgressbar', thickness=10, troughcolor='#e0e0e0', background='#4CAF50')

    # --- Marco de Selección de Archivo ---
    file_frame = tk.LabelFrame(master, text="Selección de Archivo", padx=15, pady=15, bg="#ffffff", bd=2, relief="groove")
    file_frame.pack(pady=15, padx=20, fill="x") # Este marco no necesita expandirse verticalmente

    global entry_file_path, label_duration
    tk.Label(file_frame, text="Ruta del archivo de video/audio:", bg="#ffffff").pack(pady=(0, 5), anchor="w")
    entry_file_path = tk.Entry(file_frame, width=60)
    entry_file_path.pack(pady=5, fill="x")

    label_duration = tk.Label(file_frame, text="Duración del medio: 00:00:00", bg="#ffffff")
    label_duration.pack(pady=5, anchor="w")

    tk.Button(file_frame, text="Seleccionar archivo", command=lambda: select_file(entry_file_path, label_duration)).pack(pady=10, fill="x")
    tk.Label(file_frame, text="(Arrastre y suelte el archivo aquí si tiene TkDND instalado localmente)", 
             fg="gray", font=('Inter', 8, 'italic'), bg="#ffffff").pack(pady=(0, 5))


    # --- Marco de Visualización de Onda ---
    waveform_outer_frame = tk.LabelFrame(master, text="Visualizador de Onda", padx=15, pady=15, bg="#ffffff", bd=2, relief="groove")
    waveform_outer_frame.pack(pady=15, padx=20, fill="both", expand=True)

    # Marco para las etiquetas de tiempo de selección
    selection_time_labels_frame = tk.Frame(waveform_outer_frame, bg="#ffffff")
    selection_time_labels_frame.pack(fill="x", pady=(0, 5))

    global selected_start_time_label, selected_end_time_label
    selected_start_time_label = tk.Label(selection_time_labels_frame, text="Inicio: 00:00:00", bg="#ffffff", fg="red", font=('Inter', 9, 'bold'))
    selected_start_time_label.pack(side="left", padx=10)
    selected_end_time_label = tk.Label(selection_time_labels_frame, text="Fin: 00:00:00", bg="#ffffff", fg="blue", font=('Inter', 9, 'bold'))
    selected_end_time_label.pack(side="right", padx=10)

    # Canvas para la guía de tiempos
    global time_ruler_canvas
    time_ruler_canvas = tk.Canvas(waveform_outer_frame, bg="#333333", height=20, bd=0, highlightthickness=0)
    time_ruler_canvas.pack(fill="x")
    time_ruler_canvas.bind("<Configure>", lambda event: draw_time_ruler(time_ruler_canvas, waveform_current_file_duration))

    # Canvas para la forma de onda
    global waveform_canvas
    waveform_canvas = tk.Canvas(waveform_outer_frame, bg="#333333", height=150, bd=0, highlightthickness=0)
    waveform_canvas.pack(fill="both", expand=True)

    # Vincula los eventos del mouse para la selección
    waveform_canvas.bind("<ButtonPress-1>", on_waveform_press)
    waveform_canvas.bind("<B1-Motion>", on_waveform_drag)
    waveform_canvas.bind("<ButtonRelease-1>", on_waveform_release)
    
    # Asegura que la forma de onda se redibuje al redimensionar
    waveform_canvas.bind("<Configure>", lambda event: draw_simulated_waveform(waveform_canvas, waveform_current_file_duration))


    # --- Marco de Selección de Tiempo ---
    time_frame = tk.LabelFrame(master, text="Selección de Tiempo (Manual)", padx=15, pady=15, bg="#ffffff", bd=2, relief="groove")
    time_frame.pack(pady=15, padx=20, fill="x") # Este marco no necesita expandirse verticalmente

    global entry_start_time, entry_end_time
    tk.Label(time_frame, text="Tiempo de inicio (hh:mm:ss):", bg="#ffffff").pack(pady=(0, 5), anchor="w")
    entry_start_time = tk.Entry(time_frame, width=15)
    entry_start_time.pack(pady=5, anchor="w")
    entry_start_time.insert(0, "00:00:00") # Tiempo de inicio por defecto

    tk.Label(time_frame, text="Tiempo de fin (hh:mm:ss):", bg="#ffffff").pack(pady=(10, 5), anchor="w")
    entry_end_time = tk.Entry(time_frame, width=15)
    entry_end_time.pack(pady=5, anchor="w")
    entry_end_time.insert(0, "00:00:00") # Se actualizará con la selección de archivo


    # --- Marco de Configuración de Salida ---
    output_frame = tk.LabelFrame(master, text="Configuración de Salida", padx=15, pady=15, bg="#ffffff", bd=2, relief="groove")
    output_frame.pack(pady=15, padx=20, fill="x") # Este marco no necesita expandirse verticalmente

    global entry_output_name, output_format_combobox
    tk.Label(output_frame, text="Nombre de salida:", bg="#ffffff").pack(pady=(0, 5), anchor="w")
    entry_output_name = tk.Entry(output_frame, width=30)
    entry_output_name.pack(pady=5, anchor="w")

    tk.Label(output_frame, text="Formato de salida:", bg="#ffffff").pack(pady=(10, 5), anchor="w")
    output_formats = [".mp4", ".mp3", ".avi", ".mov", ".mkv", ".wav", ".aac", ".flac"]
    output_format_combobox = ttk.Combobox(output_frame, values=output_formats, state="readonly", width=10)
    output_format_combobox.set(".mp4") # Formato por defecto
    output_format_combobox.pack(pady=5, anchor="w")


    # --- Botones de Acción y Estado ---
    button_frame = tk.Frame(master, bg="#f0f0f0")
    button_frame.pack(pady=10) 

    tk.Button(button_frame, text="Cortar Archivo", command=start_cut_video_thread, width=15).pack(side="left", padx=10)
    tk.Button(button_frame, text="Probar Previsualización", command=start_preview_thread, width=20).pack(side="left", padx=10)

    global status_label
    status_label = tk.Label(master, text="Listo para cortar video/audio", fg="#4CAF50", bg="#f0f0f0", font=('Inter', 10, 'bold'))
    status_label.pack(pady=10) 

    master.mainloop()

if __name__ == "__main__":
    create_video_cutter_window()
