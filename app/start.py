import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from matplotlib import pyplot as plt

import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu


st.set_page_config(
    page_title='Lost Ark Data Recorder',
    layout='wide'
)

# file paths
dir_root = Path('app').resolve()
dir_data = dir_root / 'data'
data_app = dir_data / 'appdata.json'
data_chars = dir_data / 'characters.csv'

dir_history = dir_data / 'histories'
hist_gr_csv = dir_history / 'gr.csv'
hist_cd_aor_csv = dir_history / 'cd_aor.csv'
hist_cd_ig_csv = dir_history / 'cd_ig.csv'

# load data
app_data = json.loads(data_app.read_text())
activities = app_data['activities']
bosses = app_data['bosses']
dungeons = app_data['dungeons']
specs = app_data['specs']

characters = pd.read_csv(data_chars)
hist_gr = pd.read_csv(hist_gr_csv)
hist_cd_aor = pd.read_csv(hist_cd_aor_csv)
hist_cd_ig = pd.read_csv(hist_cd_ig_csv)

has_chars = characters.shape[0] > 0

@dataclass
class Character:
    name: str
    spec: str = None
    ilvl: int = None

    def __str__(self) -> str:
        return f'{self.name} ({self.ilvl})'

def add_char(char: Character):
    (
        pd.concat([
            characters,
            pd.DataFrame([asdict(char)])
        ])
        .drop_duplicates()
        .to_csv(data_chars, index=False)
    )

def del_char(char: Character):
    (
        characters[characters['name'] != char.name]
        .to_csv(data_chars, index=False)
    )

def get_char(name: str):
    char = characters.set_index('name').loc[name]
    return Character(name, char.spec, char.ilvl)

def update_char(char: Character):
    row = characters[characters['name'] == char.name]
    characters.at[row.index.values[0], 'ilvl'] = char.ilvl
    characters.to_csv(data_chars, index=False)

def fmt(string):
    return string.replace('_', ' ').title()

def timestamp():
    return datetime.now().strftime('%Y-%m-%d-%H:%M:%S')

def char_edit_menu():
    st.subheader('Add Character')
    with st.form('char_submit_form', clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input('Name')
        spec = c2.selectbox('Spec', specs, key='spec_select')
        level = c3.number_input('ilvl', min_value=0, max_value=1500, step=25, value=1100)
        if st.form_submit_button('Add Character'):
            add_char(Character(name, spec, level))
            st.experimental_rerun()
    
    if characters.shape[0] > 0:
        st.subheader('Update Character')
        with st.container():
            c1, c2 = st.columns(2)
            name = c1.selectbox(
                label='Name',
                options=characters['name'].values,
                key='update_select')
            ilvl = c2.number_input(
                label='ilvl',
                min_value=0,
                max_value=1500,
                step=25,
                value=characters.set_index('name').loc[name, 'ilvl'])
            if st.button('Update Character'):
                update_char(Character(name=name, ilvl=ilvl))
                st.experimental_rerun()
        
        st.subheader('Delete Character')
        name = st.selectbox('Name', characters['name'].values)
        if st.button('Delete Character'):
            del_char(Character(name))
            st.experimental_rerun()

def character_page():
    if has_chars:
        st.subheader('Registered Characters')
        # hides index column in table display
        st.markdown(
            """
            <style>
            tbody th {display:none}
            .blank {display:none}
            </style>
            """,
            unsafe_allow_html=True
        )
        st.table(characters.sort_values('ilvl', ascending=False))
    char_edit_menu()

def record_page():
    if not has_chars:
        st.error('Please register a character first')
        st.stop()

    c1, c2, c3 = st.columns(3)
    char_name = c1.selectbox('Character', options=characters)
    activity_type = c2.selectbox('Activity', options=activities)

    # check character level vs activity requirements
    char = get_char(char_name)
    at_level = True

    match activities.index(activity_type):
        case 0 | 1:
            selected_dungeon = c3.selectbox('Dungeon', list(dungeons))
            required_ilvl = dungeons[selected_dungeon]
            for k, v in dungeons.items():
                if v <= char.ilvl:
                    max_available = k
            if char.ilvl < required_ilvl:
                st.error(f'{char} ilvl is too low for {selected_dungeon} ({required_ilvl})')
                st.stop()
            elif selected_dungeon != max_available:
                st.info(f'Overleveled: {selected_dungeon} ({required_ilvl}) is below the highest available for {char}')
                at_level = False
        case 2:
            selected_boss = c3.selectbox('Boss', list(bosses))
            required_ilvl = bosses[selected_boss]
            for k, v in bosses.items():
                if v <= char.ilvl:
                    max_available = k
            if char.ilvl < required_ilvl:
                st.error(f'{char}) ilvl is too low for {selected_boss} ({required_ilvl})')
                st.stop()
            elif selected_boss != max_available:
                st.info(f'Overleveled: {selected_boss} ({required_ilvl}) is below the highest available for {char})')
                at_level = False

    # activity recording forms
    match activities.index(activity_type):
        # chaos w/ aor
        case 0:
            start_values, end_values = {}, {}
            categories = ('red', 'blue', 'leapstones', 'greater_leapstones', 'shards')
            num_categories = len(categories)

            with st.form('chaos_dng_aor_form', clear_on_submit=True):
                for key, data in [
                    ('starting_counts', start_values),
                    ('ending_counts', end_values),
                ]:
                    st.subheader(fmt(key))
                    for k, c in zip(categories, st.columns(num_categories)):
                        data[k] = c.number_input(fmt(k), value=0, key=f'{k}_{key}')
                
                bonus_floor = st.radio('Bonus Floor', options=['None', 'Boss', 'Treasure'])
                bonus_rested = st.checkbox('Rested Bonus')

                if st.form_submit_button():
                    counts = {k: end_values[k] - start_values[k] for k in categories}
                    (
                        pd.concat([
                            hist_cd_aor,
                            pd.DataFrame([{
                                'timestamp': timestamp(),
                                'character': char.name,
                                'ilvl': char.ilvl,
                                'dungeon': selected_dungeon,
                                'at_level': at_level,
                                'rested': bonus_rested == 1,
                                'bonus_floor': bonus_floor,
                                **counts
                            }])
                        ])
                        .to_csv(hist_cd_aor_csv, index=False)
                    )
        
        # chaos infinite grind
        case 1:
            categories = ('currency_orbs', 'currency_shards', 'red', 'blue')
            num_categories = len(categories)
            start_values = {}
            f1_values = {}
            f2_values = {}
            f3_values = {}

            with st.form('chaos_dng_ig_form', clear_on_submit=True):
                for key, data in [
                    ('starting_counts', start_values),
                    ('floor_1_counts', f1_values),
                    ('floor_2_counts', f2_values),
                    ('floor_3_counts', f3_values)
                ]:
                    st.subheader(fmt(key))
                    for k, c in zip(categories, st.columns(len(categories))):
                        data[k] = c.number_input(fmt(k), value=0, key=f'{k}_{key}')

                bonus_floor = st.checkbox('Treasure/Boss Floor')

                if st.form_submit_button():
                    base_record = {
                        'timestamp': timestamp(),
                        'character': char.name,
                        'ilvl': char.ilvl,
                        'dungeon': selected_dungeon,
                        'at_level': at_level,
                        'bonus_floor': bonus_floor == 1
                    }

                    counts = [
                        {k: end[k] - start[k] for k in categories}
                        for end, start in [
                            (f1_values, start_values),
                            (f2_values, f1_values),
                            (f3_values, f2_values)
                        ]
                    ]

                    (
                        pd.concat([
                            hist_cd_ig,
                            pd.DataFrame([
                                base_record | {'floor': floor} | data
                                for floor, data in enumerate(counts, start=1)
                            ])
                        ])
                        .to_csv(hist_cd_ig_csv, index=False)
                    )
        
        # guardian raid
        case 2:
            start_values, end_values = {}, {}
            categories = ('red', 'blue', 'leapstones', 'greater_leapstones')
            num_categories = len(categories)
                        
            with st.form('gr_form', clear_on_submit=True):
                for key, data in [
                    ('starting_counts', start_values),
                    ('ending_counts', end_values),
                ]:
                    st.subheader(fmt(key))
                    for k, c in zip(categories, st.columns(num_categories)):
                        data[k] = c.number_input(fmt(k), value=0, key=f'{k}_{key}')
                
                bonus_rested = st.checkbox('Rested Bonus')
                bonus_first = st.checkbox('First Time Bonus')
              
                if st.form_submit_button():
                    counts = {k: end_values[k] - start_values[k] for k in categories}
                    (
                        pd.concat([
                            hist_gr,
                            pd.DataFrame([{
                                'timestamp': timestamp(),
                                'character': char.name,
                                'ilvl': char.ilvl,
                                'boss': selected_boss,
                                'at_level': at_level,
                                'rested': bonus_rested == 1,
                                'first_time': bonus_first == 1,
                            } | {
                                k: end_values[k] - start_values[k]
                                for k in categories
                            }])
                        ])
                        .to_csv(hist_gr_csv, index=False)
                    )

def history_page():
    for act, tbl in zip(activities, (hist_cd_aor, hist_cd_ig, hist_gr)):
        with st.expander(f'{act} ({tbl.shape[0]})'):
            st.table(tbl)


pages = ['Characters', 'Record', 'History']

active_page = option_menu(
    menu_title="Lost Ark Data Recorder",
    options=pages,
    icons=['people-fill', 'play-fill', 'server'],
    # menu_icon='cast',
    default_index=1,
    orientation='horizontal',
)

match pages.index(active_page):
    case 0:
        character_page()
    case 1:
        record_page()
    case 2:
        history_page()
