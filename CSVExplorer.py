import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import seaborn.objects as so

class CSVExplorer():
    def __init__(self): 
        self.data = None 
        # Create window    
        root = tk.Tk()
        root.title("CSV Explorer")
        root.geometry("400x200")
        # Call update to make the root window appear before creating the notebook widget
        root.update() 

        # Create notebook widget
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both')

        # Create file tab
        file_tab = ttk.Frame(self.notebook)
        self.notebook.add(file_tab, text='File')

        # Label widget to display instructions for selecting a CSV file
        file_label = ttk.Label(file_tab, text="Select a CSV file:")
        file_label.grid(row=0, column=0, padx=5, pady=5)

        # Button widget to open the file dialog and read the CSV file
        file_button = ttk.Button(file_tab, text="Select File", command=self.select_file)
        file_button.grid(row=0, column=1, padx=5, pady=5)
        
        root.mainloop()


    # Function to open the file dialog and read the CSV file into a Pandas DataFrame
    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[('CSV Files', '*.csv')])
        if file_path and file_path.endswith(".csv"):
            self.data = pd.read_csv(file_path, parse_dates=['Timestamp'])
            options = sorted(self.data['Host'].unique())
            options.append("All")

            # Create or update chart tab
            if not hasattr(self, 'chart_tab'):
                # Create chart tab
                self.chart_tab = ttk.Frame(self.notebook)
                self.notebook.add(self.chart_tab, text='Charts')

                # Label widget to display instructions for selecting a host name
                host_label = ttk.Label(self.chart_tab, text="Select a host name")
                host_label.grid(row=0, column=0, padx=5, pady=5)

                # Dropdown menu to select the host name
                self.host_var = tk.StringVar() 
                self.host_option_menu = ttk.OptionMenu(self.chart_tab, self.host_var, *options)
                self.host_option_menu.grid(row=0, column=1, padx=5, pady=5)        

                # Button widgets to create the plots for latency and packet loss
                for i, chart_option in enumerate(chart_options):
                    chart_button = ttk.Button(self.chart_tab, text=chart_option[2], command=lambda x=chart_option[1], y=chart_option[2], color=chart_option[0]: self.create_plot(x, y, color))
                    chart_button.grid(row=1, column=i, padx=5, pady=5)
            else:
                self.host_option_menu['menu'].delete(0, 'end')
                for option in options:
                    self.host_option_menu['menu'].add_command(label=option, command=tk._setit(self.host_var, option))
                self.host_var.set(options[0])

            # Switch to the Charts tab after the file is loaded
            self.notebook.select(self.chart_tab)
        else:
            messagebox.showerror("Error", "Please select a valid CSV file.")


    # Function to create a plot based on the selected host name
    def create_plot(self, x, y,color):
        if self.data is None:
            messagebox.showerror("Error", "Please select a CSV file first.")
            return
        host = self.host_var.get()
        if host == "All":
            plot_data = self.data
        elif host not in self.data['Host'].unique():
            messagebox.showerror("Error", "Please select a valid host name.")
            return
        else:
            plot_data = self.data[self.data['Host'] == host]
        plot = (so.Plot(plot_data, x=x, y=y, color=color).add(so.Line()))
        plot.show()



if __name__ == '__main__':
    chart_options = [
                    ("Host", "Timestamp", "Latency (ms)"), 
                    ("Host", "Timestamp", "Packet Loss (%)")
                ]        
    explorer = CSVExplorer()

