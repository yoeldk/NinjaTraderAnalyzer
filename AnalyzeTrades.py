import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Function to load and merge Excel files
def load_and_merge_files(uploaded_files):
    dataframes = []
    for file in uploaded_files:
        df = pd.read_excel(file)
        
        # Convert 'Profit' column to numeric, handling parentheses for negative values
        df['Profit'] = df['Profit'].replace('[\$,)]', '', regex=True).replace('[(]', '-', regex=True).astype(float)
        
        dataframes.append(df)
    merged_df = pd.concat(dataframes, ignore_index=True)
    merged_df['Entry time'] = pd.to_datetime(merged_df['Entry time'])
    return merged_df

# Function to calculate statistics
def calculate_statistics(df):
    if df.empty:
        # Return default values if the DataFrame is empty
        return 0, 0, 0, pd.DataFrame(columns=['Consecutive Loss Days', 'Start Date']), pd.DataFrame(columns=['Date', 'Profit'])

    # Convert 'Entry time' to datetime and extract the date without formatting
    df['Date'] = pd.to_datetime(df['Entry time']).dt.date
    # Group by 'Date' (as datetime.date) for accurate aggregation
    trades_per_day = df.groupby('Date').size().mean()
    profit_per_day = df.groupby('Date')['Profit'].sum().mean()
    profit_per_month = df.groupby(df['Entry time'].dt.to_period('M'))['Profit'].sum().mean()

    # Calculate consecutive loss days
    daily_profits = df.groupby('Date')['Profit'].sum()
    loss_days = daily_profits < 0  # Only consider days with negative profit

    # Identify streaks by grouping consecutive loss days
    streak_id = (loss_days != loss_days.shift()).cumsum()
    loss_streaks = loss_days.groupby(streak_id).agg(['sum', 'min'])

    # Filter only the loss streaks with length >=1
    valid_streaks = loss_streaks[(loss_streaks['min'] == True) & (loss_streaks['sum'] >= 1)]

    # Get start dates of valid loss streaks
    streak_start_dates = loss_days.groupby(streak_id).apply(lambda x: x.index[0])
    streak_start_dates = streak_start_dates[valid_streaks.index]

    # Create DataFrame for plotting
    streaks_df = pd.DataFrame({
        'Consecutive Loss Days': valid_streaks['sum'].astype(int),
        'Start Date': pd.to_datetime(streak_start_dates).dt.strftime('%d-%m-%Y')
    }).reset_index(drop=True)

    return trades_per_day, profit_per_day, profit_per_month, streaks_df, daily_profits

# Streamlit app
st.title("Trade Analysis App")

# Sidebar for file upload
uploaded_files = st.sidebar.file_uploader("Upload Excel files", accept_multiple_files=True, type=['xls', 'xlsx'])

if uploaded_files:
    # Load and merge files
    merged_df = load_and_merge_files(uploaded_files)
    merged_df = merged_df.sort_values(by='Entry time')

    # Display merged table
    st.subheader("Merged Trade Data")
    st.dataframe(merged_df)

    # Get unique strategies
    unique_strategies = merged_df['Strategy'].unique()

    # Sidebar for strategy selection with checkboxes
    st.sidebar.subheader("Select Strategies")
    select_all = st.sidebar.checkbox("Select/Deselect All", value=True)
    selected_strategies = []
    for strategy in unique_strategies:
        if st.sidebar.checkbox(strategy, value=select_all):
            selected_strategies.append(strategy)

    # Filter data based on selected strategies
    filtered_df = merged_df[merged_df['Strategy'].isin(selected_strategies)]

    # Calculate and display statistics
    trades_per_day, profit_per_day, profit_per_month, streaks_df, daily_profits = calculate_statistics(filtered_df)

    st.subheader("Statistics")
    st.write(f"Average number of trades per day: {trades_per_day:.2f}")
    st.write(f"Average profit/loss per day: ${profit_per_day:.2f}")
    st.write(f"Average profit/loss per month: ${profit_per_month:.2f}")

    # Plot histogram of consecutive loss days using Plotly
    st.subheader("Consecutive Loss Days Histogram")

    # Ensure each streak is treated as a separate entity
    streaks_df['Streak ID'] = streaks_df.index

    grouped_streaks = (
        streaks_df
        .groupby('Consecutive Loss Days', as_index=False)
        .agg({'Start Date': list})
    )

    # Count how many streaks per length
    grouped_streaks['Count'] = grouped_streaks['Start Date'].apply(len)

    # Truncate hover text to a maximum number of dates
    max_dates_in_tooltip = 10
    grouped_streaks['All Start Dates'] = grouped_streaks['Start Date'].apply(
        lambda dates: '<br>'.join(str(d) for d in dates[:max_dates_in_tooltip]) + ('<br>...' if len(dates) > max_dates_in_tooltip else '')
    )

    # Create a bar chart that acts like a histogram
    fig = px.bar(
        grouped_streaks,
        x='Consecutive Loss Days',
        y='Count',
        title='Histogram of Consecutive Loss Days',
        labels={'Consecutive Loss Days': 'Consecutive Loss Days', 'Count': 'Count'},
        hover_data=['All Start Dates'],
    )
    fig.update_traces(
        hovertemplate=(
            'Consecutive Loss Days: %{x}<br>'
            'Count: %{y}<br>'
            'Start Dates:<br>%{customdata[0]}<extra></extra>'
        )
    )

    fig.update_xaxes(type='category')
    fig.update_traces(customdata=grouped_streaks[['All Start Dates']])

    st.plotly_chart(fig)

    # Plot profit/loss per day
    st.subheader("Profit/Loss Per Day")
    # Ensure the index is datetime for accurate plotting
    daily_profits = daily_profits.reset_index()
    daily_profits['Date'] = pd.to_datetime(daily_profits['Date'])

    # Add markers to the line plot for better hover interaction
    profit_loss_fig = px.line(
        daily_profits, 
        x='Date', 
        y='Profit', 
        labels={'Date': 'Date', 'Profit': 'Profit/Loss'}, 
        title='Profit/Loss Per Day',
        markers=True  # Add this line to include markers
    )

    st.plotly_chart(profit_loss_fig)
