function showSection(sectionId){

const sections = document.querySelectorAll(".section");

sections.forEach(sec=>{
sec.classList.remove("active");
});

document.getElementById(sectionId).classList.add("active");

}



async function uploadImage(){

const input = document.getElementById("imageInput");

if(input.files.length === 0){
alert("Please upload an image.");
return;
}

const file = input.files[0];

const formData = new FormData();
formData.append("file",file);

document.getElementById("loading").classList.remove("hidden");

try{

const response = await fetch("http://localhost:8000/recognize",{
method:"POST",
body:formData
});

const data = await response.json();

document.getElementById("preview").src = URL.createObjectURL(file);

document.getElementById("plate").innerText = data.plate_number;

document.getElementById("confidence").innerText = data.confidence;

document.getElementById("vehicleInfo").innerHTML =
`Owner: ${data.owner} <br>
Vehicle: ${data.vehicle} <br>
City: ${data.city}`;

document.getElementById("result").classList.remove("hidden");

addToHistory(data);

}catch(error){

alert("Backend connection failed");

}

document.getElementById("loading").classList.add("hidden");

}



function addToHistory(data){

const container = document.getElementById("historyContainer");

const item = document.createElement("div");

item.classList.add("history-item");

item.innerHTML = `Plate: ${data.plate_number} | Confidence: ${data.confidence}`;

container.prepend(item);

}