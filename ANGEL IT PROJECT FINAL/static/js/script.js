function searchLuggage() {

    const trackingID =
        document.getElementById("trackingID").value.trim();

    const result =
        document.getElementById("searchResult");


    // =========================
    // EMPTY SEARCH
    // =========================

    if (trackingID === "") {

        result.innerHTML = `
            <div class="tracking-error">

                <h2>⚠️ Tracking ID Required</h2>

                <p>
                    Please enter a luggage tracking ID.
                </p>

            </div>
        `;

        return;
    }


    // =========================
    // SEARCH LUGGAGE
    // =========================

    fetch(`/track?id=${encodeURIComponent(trackingID)}`)

        .then(response => response.json())

        .then(data => {

            if (data.success) {

                const luggage = data.luggage;


                // =========================
                // GET JOURNEY STATUS
                // =========================

                const journeyStatus =
                    luggage.journey_status ||
                    luggage.status;


                // =========================
                // GET ALERT STATUS
                // =========================

                const alertStatus =
                    luggage.alert_status;


                // =========================
                // DETERMINE CURRENT STAGE
                // =========================

                let currentStage = 1;


                if (
                    journeyStatus === "Checked In"
                ) {

                    currentStage = 1;

                }

                else if (
                    journeyStatus === "Loaded onto Aircraft"
                ) {

                    currentStage = 2;

                }

                else if (
                    journeyStatus === "In Transit"
                ) {

                    currentStage = 3;

                }

                else if (
                    journeyStatus === "Arrived at Destination"
                ) {

                    currentStage = 4;

                }

                else if (
                    journeyStatus === "Ready for Collection"
                ) {

                    currentStage = 5;

                }

                else if (
                    journeyStatus === "Collected"
                ) {

                    currentStage = 6;

                }


                // =========================
                // BUILD ALERT
                // =========================

                let alertHTML = "";


                if (
                    alertStatus === "Delayed"
                ) {

                    alertHTML = `

                        <div class="tracking-alert delayed-alert">

                            <h3>
                                ⚠️ Luggage Delayed
                            </h3>

                            <p>
                                Your luggage has been delayed.
                                Please see the latest information
                                below.
                            </p>

                        </div>

                    `;

                }


                else if (
                    alertStatus === "Lost"
                ) {

                    alertHTML = `

                        <div class="tracking-alert lost-alert">

                            <h3>
                                🚨 Luggage Reported Lost
                            </h3>

                            <p>
                                Your luggage has been reported
                                as lost. Please contact ANGEL
                                support for assistance.
                            </p>

                        </div>

                    `;

                }


                // =========================
                // JOURNEY STAGES
                // =========================

                const stages = [

                    "Checked In",

                    "Loaded onto Aircraft",

                    "In Transit",

                    "Arrived at Destination",

                    "Ready for Collection",

                    "Collected"

                ];


                let progressHTML = "";


                stages.forEach((stage, index) => {

                    const stageNumber = index + 1;

                    let stageClass = "";


                    // Completed

                    if (
                        stageNumber < currentStage
                    ) {

                        stageClass = "completed";

                    }


                    // Current

                    else if (
                        stageNumber === currentStage
                    ) {

                        stageClass = "current";

                    }


                    progressHTML += `

                        <div class="tracking-stage ${stageClass}">

                            <div class="stage-circle">

                                ${
                                    stageNumber < currentStage
                                    ? "✓"
                                    : stageNumber
                                }

                            </div>


                            <div class="stage-name">

                                ${stage}

                            </div>

                        </div>

                    `;


                    // Connecting line

                    if (
                        stageNumber < stages.length
                    ) {

                        progressHTML += `

                            <div class="stage-line"></div>

                        `;

                    }

                });


                // =========================
                // DISPLAY RESULT
                // =========================

                result.innerHTML = `

                    <div class="tracking-result">


                        <h2>
                            ✓ Luggage Found
                        </h2>


                        <!-- ALERT -->

                        ${alertHTML}


                        <!-- LUGGAGE INFORMATION -->

                        <p>

                            <strong>
                                Tracking ID:
                            </strong>

                            ${data.tracking_id}

                        </p>


                        <p>

                            <strong>
                                Passenger:
                            </strong>

                            ${luggage.passenger}

                        </p>


                        <p>

                            <strong>
                                Flight:
                            </strong>

                            ${luggage.flight}

                        </p>


                        <p>

                            <strong>
                                Route:
                            </strong>

                            ${luggage.from}
                            →
                            ${luggage.to}

                        </p>


                        <p>

                            <strong>
                                Weight:
                            </strong>

                            ${luggage.weight}

                        </p>


                        <p>

                            <strong>
                                Status:
                            </strong>

                            ${journeyStatus}

                        </p>


                        <p>

                            <strong>
                                Current Location:
                            </strong>

                            ${luggage.location}

                        </p>


                        <!-- LIVE STATUS -->

                        <div class="journey-container">

                            <h3>
                                Live Status
                            </h3>


                            <div class="journey">

                                ${progressHTML}

                            </div>

                        </div>


                    </div>

                `;

            }


            // =========================
            // NOT FOUND
            // =========================

            else {

                result.innerHTML = `

                    <div class="tracking-error">

                        <h2>
                            ✕ Luggage Not Found
                        </h2>

                        <p>
                            ${data.message}
                        </p>

                    </div>

                `;

            }

        })


        // =========================
        // CONNECTION ERROR
        // =========================

        .catch(error => {

            console.error(
                "Error:",
                error
            );


            result.innerHTML = `

                <div class="tracking-error">

                    <h2>
                        Something went wrong
                    </h2>

                    <p>
                        Unable to connect to the
                        ANGEL tracking system.
                    </p>

                </div>

            `;

        });

}