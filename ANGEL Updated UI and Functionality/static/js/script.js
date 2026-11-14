
function searchLuggage() {

    const trackingID =
        document.getElementById("trackingID").value.trim();

    const result =
        document.getElementById("searchResult");

    // Safely display information returned by the database

    function escapeHTML(value) {

        const element = document.createElement("div");

        element.textContent = String(value ?? "Not available");

        return element.innerHTML;
    }

    // EMPTY SEARCH

    if (trackingID === "") {

        result.innerHTML = `
            <div class="tracking-error">
                <h2>Tracking ID Required</h2>
                <p>Please enter a luggage tracking ID.</p>
            </div>
        `;

        return;
    }

    // LOADING STATE

    result.innerHTML = `
        <div class="angel-tracking-loading">
            <div class="angel-loading-spinner"></div>
            <p>Locating your luggage...</p>
        </div>
    `;

    // SEARCH LUGGAGE

    fetch(`/track?id=${encodeURIComponent(trackingID)}`)

        .then(response => response.json())

        .then(data => {

            if (data.success) {

                const luggage = data.luggage;

                const journeyStatus =
                    luggage.journey_status ||
                    luggage.status;

                const alertStatus =
                    luggage.alert_status;

                // ALL SIX JOURNEY STAGES

                const stages = [

                    "Checked In",

                    "Loaded onto Aircraft",

                    "In Transit",

                    "Arrived at Destination",

                    "Ready for Collection",

                    "Collected"

                ];

                const currentStage =
                    stages.indexOf(journeyStatus) + 1;

                // LUGGAGE ALERTS

                let alertHTML = "";

                if (alertStatus === "Delayed") {

                    alertHTML = `
                        <div class="tracking-alert delayed-alert">

                            <h3>Luggage Delayed</h3>

                            <p>
                                Your luggage has been delayed.
                                Please see the latest information below.
                            </p>

                        </div>
                    `;

                }

                else if (alertStatus === "Lost") {

                    alertHTML = `
                        <div class="tracking-alert lost-alert">

                            <h3>Luggage Reported Lost</h3>

                            <p>
                                Your luggage has been reported
                                as lost. Please contact ANGEL
                                support for assistance.
                            </p>

                        </div>
                    `;

                }

                // BUILD PREMIUM JOURNEY TIMELINE

                let progressHTML = "";

                stages.forEach((stage, index) => {

                    const stageNumber = index + 1;

                    let stageClass = "";

                    if (stageNumber < currentStage) {

                        stageClass = "completed";

                    }

                    else if (stageNumber === currentStage) {

                        stageClass = "current";

                    }

                    progressHTML += `

                        <div class="angel-timeline-stage ${stageClass}"
                             ${stageClass === "current"
                                 ? 'aria-current="step"'
                                 : ''}>

                            <div class="angel-stage-marker">

                                ${
                                    stageNumber < currentStage
                                    ? "✓"
                                    : stageNumber
                                }

                            </div>

                            <div class="angel-stage-content">

                                <strong>${stage}</strong>

                                ${
                                    stageNumber === currentStage
                                    ? "<span>Current recorded stage</span>"
                                    : ""
                                }

                            </div>

                        </div>

                    `;

                });

                // DISPLAY PREMIUM TRACKING RESULT

                result.innerHTML = `

                    <div class="angel-result">

                        <div class="angel-result-success">

                            <i class="bi bi-check-circle"></i>

                            Luggage record found

                        </div>

                        ${alertHTML}

                        <!-- DIGITAL LUGGAGE TICKET -->

                        <div class="angel-luggage-ticket">

                            <div class="angel-ticket-top">

                                <div>

                                    <span class="angel-ticket-label">
                                        ANGEL TRACKING REFERENCE
                                    </span>

                                    <h2>
                                        ${escapeHTML(data.tracking_id)}
                                    </h2>

                                </div>

                                <i class="bi bi-briefcase"></i>

                            </div>

                            <div class="angel-ticket-route">

                                <div class="angel-route-origin">

                                    <span>DEPARTURE</span>

                                    <h3>
                                        ${escapeHTML(luggage.from)}
                                    </h3>

                                </div>

                                <div class="angel-route-plane">

                                    <i class="bi bi-airplane"></i>

                                </div>

                                <div class="angel-route-destination">

                                    <span>DESTINATION</span>

                                    <h3>
                                        ${escapeHTML(luggage.to)}
                                    </h3>

                                </div>

                            </div>

                        </div>

                        <!-- LUGGAGE INFORMATION -->

                        <div class="angel-result-details">

                            <div class="angel-detail">

                                <span>Passenger</span>

                                <strong>
                                    ${escapeHTML(luggage.passenger)}
                                </strong>

                            </div>

                            <div class="angel-detail">

                                <span>Flight number</span>

                                <strong>
                                    ${escapeHTML(luggage.flight)}
                                </strong>

                            </div>

                            <div class="angel-detail">

                                <span>Luggage weight</span>

                                <strong>
                                    ${escapeHTML(luggage.weight)}
                                </strong>

                            </div>

                            <div class="angel-detail">

                                <span>Last recorded location</span>

                                <strong>
                                    ${escapeHTML(luggage.location)}
                                </strong>

                            </div>

                        </div>

                        <!-- JOURNEY PROGRESS -->

                        <div class="angel-journey-progress">

                            <div class="angel-progress-heading">

                                <h3>Journey progress</h3>

                                <span class="angel-status-badge">

                                    ${escapeHTML(journeyStatus)}

                                </span>

                            </div>

                            <div class="angel-timeline">

                                ${progressHTML}

                            </div>

                        </div>

                        <div class="angel-result-note">

                            <i class="bi bi-info-circle"></i>

                            Information reflects the latest
                            recorded update in ANGEL.

                        </div>

                    </div>

                `;

            }

            // LUGGAGE NOT FOUND

            else {

                result.innerHTML = `

                    <div class="tracking-error">

                        <h2>Luggage Not Found</h2>

                        <p>
                            ${escapeHTML(data.message)}
                        </p>

                    </div>

                `;

            }

        })

        // CONNECTION ERROR

        .catch(error => {

            console.error("Error:", error);

            result.innerHTML = `

                <div class="tracking-error">

                    <h2>Something went wrong</h2>

                    <p>
                        Unable to connect to the
                        ANGEL tracking system.
                        Please try again.
                    </p>

                </div>

            `;

        });

}
