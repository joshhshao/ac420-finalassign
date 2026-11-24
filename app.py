import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Airline Route Profitability",
    layout="wide",
)

st.title("✈️ Airline Route Profitability")
st.write(
    "Explore real U.S. route traffic and estimate profitability "
    "using adjustable financial assumptions."
)

st.info(
    "This app uses reported traffic data, but the financial results "
    "are estimates. Actual route revenue and costs are not available "
    "in the T-100 traffic dataset."
)

# ---------------------------------------------------
# 1. Load traffic data
# ---------------------------------------------------

uploaded_file = st.sidebar.file_uploader(scheduled_passenger_segements.csv),
    type="csv",
)

if uploaded_file is None:
    st.warning(
        "Upload a BTS T-100 Domestic Segment CSV to get started. "
        "See the instructions below for the required columns."
    )
    st.stop()

try:
    df = pd.read_csv(uploaded_file)

    # BTS downloads may have upper- or lowercase column names.
    df.columns = df.columns.str.strip().str.upper()

    # Some downloads use DEP_PERFORMED for departures.
    if "DEP_PERFORMED" in df.columns:
        df = df.rename(
            columns={"DEP_PERFORMED": "DEPARTURES_PERFORMED"}
        )

except Exception as error:
    st.error(f"Could not read the file: {error}")
    st.stop()

required_columns = [
    "ORIGIN",
    "DEST",
    "PASSENGERS",
    "SEATS",
    "DEPARTURES_PERFORMED",
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:
    st.error(
        "Your file is missing these columns: "
        + ", ".join(missing_columns)
    )
    st.stop()

# Convert traffic columns to numeric values.
numeric_columns = [
    "PASSENGERS",
    "SEATS",
    "DEPARTURES_PERFORMED",
]

for column in numeric_columns:
    df[column] = pd.to_numeric(df[column], errors="coerce")

df = df.dropna(
    subset=[
        "ORIGIN",
        "DEST",
        "PASSENGERS",
        "SEATS",
        "DEPARTURES_PERFORMED",
    ]
)

df = df[
    (df["PASSENGERS"] >= 0)
    & (df["SEATS"] > 0)
    & (df["DEPARTURES_PERFORMED"] > 0)
].copy()

if df.empty:
    st.error("There are no usable rows in this file.")
    st.stop()

# ---------------------------------------------------
# 2. Select a route
# ---------------------------------------------------

st.sidebar.header("Route selection")

origins = sorted(df["ORIGIN"].unique())

origin = st.sidebar.selectbox(
    "Origin airport",
    origins,
)

destinations = sorted(
    df.loc[df["ORIGIN"] == origin, "DEST"].unique()
)

destination = st.sidebar.selectbox(
    "Destination airport",
    destinations,
)

route_data = df[
    (df["ORIGIN"] == origin)
    & (df["DEST"] == destination)
]

passengers = route_data["PASSENGERS"].sum()
seats = route_data["SEATS"].sum()
departures = route_data["DEPARTURES_PERFORMED"].sum()

load_factor = passengers / seats

# ---------------------------------------------------
# 3. Financial assumptions
# ---------------------------------------------------

st.sidebar.header("Revenue assumptions")

revenue_per_passenger = st.sidebar.number_input(
    "Revenue per passenger ($)",
    min_value=0.0,
    value=200.0,
    step=10.0,
    help=(
        "Estimated revenue attributable to this flight segment. "
        "This may differ from the full ticket price."
    ),
)

cargo_revenue_per_flight = st.sidebar.number_input(
    "Cargo revenue per flight ($)",
    min_value=0.0,
    value=1000.0,
    step=100.0,
)

st.sidebar.header("Cost assumptions per flight")

fuel_gallons = st.sidebar.number_input(
    "Fuel used per flight (gallons)",
    min_value=0.0,
    value=3500.0,
    step=100.0,
)

fuel_price = st.sidebar.number_input(
    "Fuel price per gallon ($)",
    min_value=0.0,
    value=3.0,
    step=0.1,
)

crew_cost = st.sidebar.number_input(
    "Crew cost ($)",
    min_value=0.0,
    value=3000.0,
    step=100.0,
)

airport_cost = st.sidebar.number_input(
    "Airport and ground costs ($)",
    min_value=0.0,
    value=2500.0,
    step=100.0,
)

maintenance_cost = st.sidebar.number_input(
    "Maintenance cost ($)",
    min_value=0.0,
    value=2000.0,
    step=100.0,
)

other_cost = st.sidebar.number_input(
    "Other costs ($)",
    min_value=0.0,
    value=3000.0,
    step=100.0,
)

# ---------------------------------------------------
# 4. Calculate the scenario
# ---------------------------------------------------

fuel_cost_per_flight = fuel_gallons * fuel_price

total_cost_per_flight = (
    fuel_cost_per_flight
    + crew_cost
    + airport_cost
    + maintenance_cost
    + other_cost
)

passenger_revenue = passengers * revenue_per_passenger
cargo_revenue = departures * cargo_revenue_per_flight

total_revenue = passenger_revenue + cargo_revenue
total_cost = departures * total_cost_per_flight

estimated_profit = total_revenue - total_cost

# Revenue from cargo reduces the amount that must be
# covered by passengers.
cost_to_cover_with_passengers = max(
    0.0,
    total_cost - cargo_revenue,
)

if revenue_per_passenger > 0:
    break_even_load_factor = (
        cost_to_cover_with_passengers
        / (seats * revenue_per_passenger)
    )
else:
    break_even_load_factor = None

# ---------------------------------------------------
# 5. Display traffic data
# ---------------------------------------------------

st.subheader(f"Route: {origin} → {destination}")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Passengers", f"{passengers:,.0f}")
col2.metric("Available seats", f"{seats:,.0f}")
col3.metric("Departures", f"{departures:,.0f}")
col4.metric("Load factor", f"{load_factor:.1%}")

st.caption(
    "Traffic figures are summed across all matching rows in the "
    "uploaded file. A connecting passenger may be counted on each "
    "flight segment they travel."
)

# ---------------------------------------------------
# 6. Display financial results
# ---------------------------------------------------

st.subheader("Estimated financial scenario")

col1, col2, col3 = st.columns(3)

col1.metric("Estimated revenue", f"${total_revenue:,.0f}")
col2.metric("Estimated costs", f"${total_cost:,.0f}")
col3.metric("Estimated profit / loss", f"${estimated_profit:,.0f}")

if break_even_load_factor is None:
    st.write(
        "Break-even load factor cannot be calculated when "
        "revenue per passenger is zero."
    )
else:
    st.write(
        f"**Break-even load factor:** "
        f"{break_even_load_factor:.1%}"
    )

    if break_even_load_factor > 1:
        st.warning(
            "This scenario requires more than 100% of available "
            "seats to break even. Review the fare and cost assumptions."
        )

st.caption(
    "Break-even assumes the entered passenger revenue and cargo "
    "revenue stay constant as the number of passengers changes."
)

# ---------------------------------------------------
# 7. Show cost breakdown
# ---------------------------------------------------

st.subheader("Estimated cost per flight")

cost_breakdown = pd.DataFrame(
    {
        "Cost category": [
            "Fuel",
            "Crew",
            "Airport and ground",
            "Maintenance",
            "Other",
        ],
        "Cost ($)": [
            fuel_cost_per_flight,
            crew_cost,
            airport_cost,
            maintenance_cost,
            other_cost,
        ],
    }
)

st.bar_chart(
    cost_breakdown.set_index("Cost category")
)

with st.expander("View selected traffic rows"):
    st.dataframe(route_data, use_container_width=True)

with st.expander("How the model works"):
    st.markdown(
        """
        - **Load factor** = passengers ÷ available seats
        - **Passenger revenue** = passengers × revenue per passenger
        - **Cargo revenue** = departures × cargo revenue per flight
        - **Fuel cost per flight** = gallons used × price per gallon
        - **Estimated profit/loss** = total revenue − total cost
        - **Break-even load factor** = costs remaining after cargo
          revenue ÷ (available seats × revenue per passenger)
        """
    )
```
