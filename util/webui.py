import gradio as gr
import requests
import json
import humanize

# Function to fetch configuration from the API
def fetch_config():
    response = requests.get('http://localhost:8008/api/config').json()
    return response

# Function to fetch log entries (dummy implementation)
def fetch_logs():
    response = requests.get('http://localhost:8008/api/logs').json()
    return '\n'.join(response)
    logs=[]
    for chan in response:
      for msg in response[chan]:
        for m in response[chan][msg]:
          logs.append('<%s:#%s> %s' % (m['user'], msg, m['msg']))
          logs.append('<howsy:#%s> %s' % (msg, m['response']))
    print('Got',len(logs),'logs')

# Function to update persona (dummy implementation)
def update_persona(selected_persona, persona_text):
    response = requests.post('http://localhost:8008/api/persona', json={'persona': selected_persona, 'text': persona_text}).json()
    # Here, you would normally send the updated persona data to your application
    return response['text']

# Function to display the config as a table
def display_config():
    #config_data = fetch_config()
    #cfg = 'mode backend persona totaluptime length temperature debug logging'.split()
    #config_items = config_data.items()
    #print(config_items)
    #config = {k: config_data[k] for k in cfg if k in config_data}
    #print('Got ',len(config),' configuration variables.')
    #conf = {'user': 'whosthat', 'stuff': 'comeon'}
    return [['mode', 'bot'], ['backend', 'llamacpp'], ['persona', 'howsy'], ['totaluptime', '13603467'], ['length', '512'], ['temperature', '1'], ['debug', 'False'], ['logging', 'True']]
    #return [[str(k), str(v)] for k, v in config.items()]
    #return [(x, config_data[x]) for x in cfg]

def on_persona_selected(persona_name):
    return fetch_config()['personas'][persona_name]

# Create Gradio interface
with gr.Blocks() as demo:
    
    gr.Markdown("## Configuration")
    config_table = gr.DataFrame(headers=["Variable", "Value"], type='array', datatype=["str", "str"])
    update_button = gr.Button("Update Configuration")
    config = fetch_config()
    gr.Markdown(f"### Bot: {config['nickname']} - Up {humanize.naturaldelta(config['totaluptime'])}")
    
    gr.Markdown("## Log Entries")
    log_text = gr.Textbox(value=fetch_logs(), lines=6, interactive=False)
    btn = gr.Button("Update info")
    btn.click(fn=fetch_logs, inputs=None, outputs=log_text)
    
    config_table.data = display_config()
    print(config_table.data)
    personas = config['personas']
    
    gr.Markdown("## Edit Persona")
   
    persona_dropdown = gr.Dropdown(choices=personas.keys(), label="Personas", value=config['persona'])
    persona_textbox = gr.Textbox(lines=5, label="Edit Persona", value=config['personas'][config['persona']])
    
    persona_dropdown.change(on_persona_selected, inputs=persona_dropdown, outputs=persona_textbox)
    submit_button = gr.Button("Update Persona")
    
    # Display config data when the interface loads

    # Update persona text when submit button is clicked
    submit_button.click(update_persona, [persona_dropdown, persona_textbox], persona_textbox)

# Launch the interface on port 8009
demo.launch(server_port=8009)
