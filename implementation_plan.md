# Dynamic Dashboard Filtering

This plan outlines the implementation to make the dashboard's "Today", "This Week", and "This Month" buttons functional, alongside adding a custom date range filter.

## User Review Required

> [!IMPORTANT]
> Some metrics represent the **current state** of your store (like "Pending Orders", "Receivable Balance", "Due Today", "Ready Orders"). Filtering these by past dates doesn't make logical sense because they are active queues. 
> 
> **Proposed Approach**:
> - The top "Current Queue" metrics (Receivable balance, Pending, Due Today, Ready) will **always** show the real-time status.
> - The "Your store this month" section, the charts, and the recent orders/payments will change based on the selected date filter.

## Open Questions

> [!WARNING]
> **Question 1**: When "Today" is selected, the chart will only have a single data point (1 day). Would you like me to change the "Today" chart to break down the data **by hour** (e.g., 9 AM, 12 PM, 3 PM), or is it okay if it just shows a single dot/flat line for today's total?
> 
> **Question 2**: For the "Total Customers" metric under the chart, should it show **New Customers Registered** in the selected date range, or should it continue to show the **All-Time Total** customers in the database?

## Proposed Changes

### `core/views.py`
#### [MODIFY] `core/views.py`
- Parse `filter` parameter from `request.GET` (`today`, `week`, `month`, `custom`).
- Parse `start_date` and `end_date` if `custom` is selected.
- Calculate the `start_dt` and `end_dt` date boundaries based on the selection.
- Update the `daily_orders` query to filter by `created_at__date__gte=start_dt` and `created_at__date__lte=end_dt`.
- Dynamically determine the number of days in the range to generate the correct number of SVG chart points.
- If the range is > 1 day, generate X points. If it's 1 day (today), adapt the graph generation to either show hourly or just a single point centered.
- Filter `recent_orders` and `recent_payments` to only show data from within the selected date range.

### `core/templates/core/dashboard.html`
#### [MODIFY] `core/templates/core/dashboard.html`
- Convert the "Today", "This Week", and "This Month" buttons into active links that pass `?filter=today`, etc.
- Add active CSS styling (e.g., solid background color) to highlight which filter is currently active.
- Add a custom date picker form (Start Date to End Date) next to the buttons.
- Update the text "Your store this month" to dynamically say "Your store this [day/week/month/period]" based on the filter.

## Verification Plan

### Manual Verification
- Click "This Week" and verify the charts scale down to 7 days of data and the URL updates to `?filter=week`.
- Select a custom date range in the past and verify the charts and order lists update accordingly.
- Verify that the X-axis dates on the charts map correctly to the selected start and end dates.
