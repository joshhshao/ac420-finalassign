import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Airline Route Profitability",
    layout="wide",
)

st.title("✈️ Airline Route Profitability")
st.write(
    "Explore real U.S. route traffic and estimate profitability based on 2025 data "
    "using adjustable financial assumptions."
)

# Fare model coefficients (estimated offline, frozen in the app)
# DOT Consumer Airfare Report Table 1a, all 2025 quarters,
# n = 8,126 route-quarters, R-squared = 0.272. Q1 is the baseline.
FARE_INTERCEPT = 192.69
FARE_PER_MILE = 0.0573
FARE_QUARTER_ADJ = {1: 0.00, 2: -11.00, 3: -15.93, 4: 4.01}


def estimate_fare(distance_miles, quarter):
    """Estimated average fare for a route, from the DOT fare model."""
    return (
        FARE_INTERCEPT
        + FARE_PER_MILE * distance_miles
        + FARE_QUARTER_ADJ[quarter]
    )
    
st.info(
    "This app uses reported traffic data, but the financial results "
    "are estimates. Actual route revenue and costs are not available "
    "in the T-100 traffic dataset."
)

# ---------------------------------------------------
# 1. Load traffic data
# ---------------------------------------------------



try:
    df = pd.read_csv("quarterly_passenger_segments_2025.csv")

    # Standardize column names.
    df.columns = df.columns.str.strip().str.upper()

    # Handle alternative names for departures.
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

st.sidebar.header("Time period")

df["QUARTER"] = pd.to_numeric(df["QUARTER"], errors="coerce")
df = df.dropna(subset=["QUARTER"]).copy()

quarters = sorted(df["QUARTER"].astype(int).unique())

quarter = st.sidebar.selectbox(
    "Select a quarter",
    quarters,
    format_func=lambda q: f"Q{q}",
)



if df.empty:
    st.warning("No data is available for this quarter.")
    st.stop()

# ---------------------------------------------------
# 2. Select a route
# ---------------------------------------------------

st.sidebar.header("Route selection")

# Create the origin menu from the full dataset.
origins = sorted(df["ORIGIN"].dropna().unique())

origin = st.sidebar.selectbox(
    "Origin airport",
    origins,
)

# Create the destination menu for the selected origin.
destinations = sorted(
    df.loc[df["ORIGIN"] == origin, "DEST"].dropna().unique()
)

destination = st.sidebar.selectbox(
    "Destination airport",
    destinations,
)
# Select an airline that operated the selected route.
carriers = sorted(
    df.loc[
        (df["ORIGIN"] == origin)
        & (df["DEST"] == destination),
        "UNIQUE_CARRIER",
    ].dropna().unique()
)

# Use names from the fuel file for the airline menu.
try:
    airline_lookup = pd.read_csv("T_F41SCHEDULE_P12A.csv")
    airline_lookup.columns = airline_lookup.columns.str.strip().str.upper()

    airline_names = (
        airline_lookup[["UNIQUE_CARRIER", "CARRIER_NAME"]]
        .dropna()
        .drop_duplicates(subset=["UNIQUE_CARRIER"])
        .set_index("UNIQUE_CARRIER")["CARRIER_NAME"]
        .to_dict()
    )

except (FileNotFoundError, KeyError):
    airline_names = {}

carrier = st.sidebar.selectbox(
    "Airline",
    carriers,
    format_func=lambda code: airline_names.get(code, code),
)

# Filter only after the route has been selected.
route_data = df[
    (df["ORIGIN"] == origin)
    & (df["DEST"] == destination)
    & (df["QUARTER"] == quarter)
    & (df["UNIQUE_CARRIER"] == carrier)
].copy()

if route_data.empty:
    st.warning(
        f"No traffic data is available for {carrier} on "
        f"{origin} → {destination} in Q{quarter}."
    )
    st.stop()

passengers = route_data["PASSENGERS"].sum()
seats = route_data["SEATS"].sum()
departures = route_data["DEPARTURES_PERFORMED"].sum()

load_factor = passengers / seats

# Calculate the average distance for the selected route.
route_data["DISTANCE"] = pd.to_numeric(
    route_data["DISTANCE"],
    errors="coerce",
)

valid_distance = route_data[
    route_data["DISTANCE"].notna()
    & (route_data["DISTANCE"] > 0)
].copy()

if valid_distance.empty:
    st.error("No valid distance is available for this route.")
    st.stop()

distance_miles = (
    valid_distance["DISTANCE"]
    * valid_distance["DEPARTURES_PERFORMED"]
).sum() / valid_distance["DEPARTURES_PERFORMED"].sum()

# These are illustrative assumptions, not reported fuel usage.
fixed_fuel_gallons = st.sidebar.number_input(
    "Fixed fuel allowance per flight (gallons)",
    min_value=0.0,
    value=500.0,
    step=50.0,
)

gallons_per_mile = st.sidebar.number_input(
    "Additional fuel per mile (gallons)",
    min_value=0.0,
    value=1.5,
    step=0.1,
)

fuel_gallons = fixed_fuel_gallons + (
    distance_miles * gallons_per_mile
)

st.sidebar.caption(
    f"Distance: {distance_miles:,.0f} miles · "
    f"Estimated fuel: {fuel_gallons:,.0f} gallons per flight"
)

# ---------------------------------------------------
# 3. Financial assumptions
# ---------------------------------------------------

st.sidebar.header("Revenue assumptions")

fare_source = st.sidebar.radio(
    "Revenue per passenger source",
    ["Regression estimate", "Manual entry"],
    help=(
        "Regression estimate uses a fare model estimated on "
        "DOT ticket data (2025). Manual entry lets you type "
        "your own assumption."
    ),
)

if fare_source == "Regression estimate":
    revenue_per_passenger = estimate_fare(distance_miles, quarter)
    st.sidebar.write(
        f"Estimated fare: **${revenue_per_passenger:,.2f}**"
    )
    st.sidebar.caption(
        f"DOT fare model: $192.69 + $0.0573 x {distance_miles:,.0f} miles "
        f"+ quarter adjustment (Q{quarter}). Estimated on 8,126 "
        "route-quarters from DOT Table 1a, 2025."
    )
else:
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

# Load reported airline fuel costs.
try:
    fuel_data = pd.read_csv("T_F41SCHEDULE_P12A.csv")
    fuel_data.columns = fuel_data.columns.str.strip().str.upper()

    for column in ["YEAR", "QUARTER", "SDOMT_GALLONS", "SDOMT_COST"]:
        fuel_data[column] = pd.to_numeric(
            fuel_data[column],
            errors="coerce",
        )

    # Match the selected airline and quarter in 2025.
    matching_fuel = fuel_data[
        (fuel_data["YEAR"] == 2025)
        & (fuel_data["QUARTER"] == quarter)
        & (fuel_data["UNIQUE_CARRIER"] == carrier)
    ].copy()

    # Keep rows with usable cost and gallon figures.
    matching_fuel = matching_fuel[
        (matching_fuel["SDOMT_GALLONS"] > 0)
        & (matching_fuel["SDOMT_COST"] >= 0)
    ]

    total_gallons = matching_fuel["SDOMT_GALLONS"].sum()
    total_fuel_cost = matching_fuel["SDOMT_COST"].sum()

    if total_gallons > 0:
        fuel_price = total_fuel_cost / total_gallons

        st.sidebar.write(
            f"Reported average fuel price: **${fuel_price:.2f}/gallon**"
        )
        st.sidebar.caption(
            f"{carrier}, scheduled domestic service, Q{quarter} 2025. "
            "This is an airline-wide average."
        )
    else:
        st.warning(
            f"No usable reported fuel data was found for "
            f"{carrier} in Q{quarter} 2025."
        )
        st.stop()

except (FileNotFoundError, KeyError) as error:
    st.error(
        "Could not load the fuel dataset. Check that the CSV is "
        f"beside app.py and has the required columns. Details: {error}"
    )
    st.stop()

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

- **Load factor** = passengers ÷ available seats      <- line 478
- **Estimated fare** = ...                            <- Piece 3 goes here
- **Passenger revenue** = passengers × revenue per passenger

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

