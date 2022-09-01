////////////////////////////// GENERAL //////////////////////////////

// check media type
var ua = navigator.userAgent;
if(ua.indexOf("iPhone") > 0 || ua.indexOf("Android") > 0 && ua.indexOf("Mobile") > 0){
	var MEDIA = "mobile";
}else if (ua.indexOf("iPad") > 0 || ua.indexOf("Android") > 0) {
	var MEDIA = "tablet";
}else{
	var MEDIA = "PC";
} 

// change language in ABOUT & HOW TO USE
function change_lang(elem){
	elem.blur();
	let jp_contents = document.querySelectorAll(".jp");
	let th_contents = document.querySelectorAll(".th");
	let btn_lang = document.querySelectorAll(".btn_lang");
	if(jp_contents[0].style.display == ""){ // if current lang is Thai
		jp_contents.forEach(x => x.style.display = "none");
		th_contents.forEach(x => x.style.display = "");
		btn_lang.forEach(x => x.innerText = "日本語");
	}else{
		jp_contents.forEach(x => x.style.display = "");
		th_contents.forEach(x => x.style.display = "none");
		btn_lang.forEach(x => x.innerText = "ภาษาไทย");
	}
}

// copy input form left <> right
function copy_input(leftright){
	if(leftright=='toright' && input_word1.trim()!=""){
		input_string1.value = input_word1.value.replace(/\|/g, '');
		input_string2.value = input_word2.value.replace(/\|/g, '');
	}else if(leftright=='toleft' && input_string1.trim()!=""){
		input_word1.value = input_string1.value;
		input_word2.value = input_string2.value;
	}
}

// toggle select/unselected of each data source
function set_source(source_btn){
	$(source_btn).toggleClass("selected_source");
	source_btn.blur();
	if(source_btn.classList.contains("selected_source")){
		source_btn.style.opacity = 1;
	}else{
		source_btn.style.opacity = 0.3;
	}
}
function unselect_all(){
	document.querySelectorAll('.selected_source').forEach(x => set_source(x));
}
function select_all(){
	document.querySelectorAll('.source:not(.selected_source)').forEach(x => set_source(x));
}

// make datalist for input
function make_list(n, present_input){
	// select datalist for input1 or 2 
	let datalist = (n==1)? datalist1 : datalist2;
	datalist.innerHTML = ""; // initialize
	// get present input
	if(present_input.length >= 3){
		var num_candidate = 0; 
		for(var vocab of VOCABS){ // VOCABS is in vocab.js
			if(vocab.startsWith(present_input)){
				datalist.innerHTML += `<option value="${vocab}">${vocab}</option>`;
				num_candidate += 1;
				if(num_candidate >= 6){break;} // show only 6 candidates
			}
		}
	}
}

////////// Press Enter Key to search //////////
document.addEventListener('keyup', function(event){
	if(event.keyCode == '13'){
		if(['input_word1', 'input_word2'].includes(document.activeElement.id)){
			start_ajax('word');
		}else if(['input_string1', 'input_string2'].includes(document.activeElement.id)){
			start_ajax('string');
		}
	}
});

////////////////////////////// SEND POST REQUEST BY AJAX //////////////////////////////

function validate_form(mode){
	// if no source is checked, alert
	let is_checked_at_least_one = document.querySelectorAll(".selected_source").length > 0;
	if(!is_checked_at_least_one){
		alert("กรุณาเลือกแหล่งข้อมูล\nデータソースを選択して下さい");
		return false;
	}
	// validate input form : mode = word or string
	// no input -> return false
	if(mode=="word" && input_word1.value.trim()==""){
		input_word1.focus();
		return false;
	}else if(mode=="string" && input_string1.value.trim() == ""){
		input_string1.focus();
		return false;
	}else{
		return true;
	}
}

function start_ajax(mode){
	// validate form, return if false 
	if(validate_form(mode)==false){
		return false;
	}
	// list of checked sources
	var sources = Array.from(document.querySelectorAll('.selected_source')).map(x => x.id); // [source_twitter, source_pantip,...]
	// delete existing wf chart
	// hide existing result rows except for mode:word_to_string
	if(mode=="word" || mode=="string"){
		word_freq_canvas.innerHTML = `<div class="col-md-12"><canvas id="wf_chart" style="width: 100%; height:300px;"></canvas></div>`;
		document.querySelectorAll(".result_row").forEach(x => x.style.display="none");
	}
	// make spinner visible & scroll to the point of spinner
	if(mode=="word"){
		loading_word.style.display = "";
		window.scrollTo({top:loading_word.getBoundingClientRect().top + window.pageYOffset - 170, behavior:"smooth"});
	}else{
		loading_string.style.display = "";
		window.scrollTo({top:loading_string.getBoundingClientRect().top + window.pageYOffset - 170, behavior:"smooth"});
	}
	// make POST parameters
	var data_to_send = {
		"mode":mode,
		"sources":sources,
		"input1":(mode=="word")? input_word1.value : input_string1.value,
		"input2":(mode=="word")? input_word2.value : input_string2.value,
		"input3":input3.value, // hidden input for word_to_string mode
		"n_left":n_left.value,
		"n_right":n_right.value,
		"use_multiple_words":use_multiple_words.checked,
		"is_regex":switch_regex.checked,
		"media": MEDIA
	};
	console.log(data_to_send);
	////////// start ajax //////////
	$.ajax({
		data : data_to_send,
		type: "POST",
		dataType: "json",
		cache: false,
		timeout: 50000,
		url : "/"
	}).done(function(returnData){
		// hide rotating spinner
		loading_word.style.display = "none";
		loading_string.style.display = "none";
		// show results
		if(mode=="word"){
			show_result_word(returnData);
		}else if(mode=="string"){
			show_result_string(returnData, mode);
		}else if(mode=="word_to_string"){
			table_onestring.innerHTML = ""; // initialize
			show_result_string(returnData, mode);
		}
	}).fail(function(){ // when fail to connet 
		// hide rotating spinner
		loading_word.style.display = "none";
		loading_string.style.display = "none";
		alert('Connection Error');
	});
}


////////////////////////////// SHOW RESULT: SEARCH BY WORD //////////////////////////////

function show_result_word(data){
	////////// get chart element //////////
	//console.log(data)
	word_freq_canvas.style.display = "";
	var chartChart = document.getElementById("wf_chart");
	////////// make dataset //////////
	var word_freq1 = data.word_freq1; // receive word freq & search time as array: [[source, wf, time],...]
	var query1 = input_word1.value;
	if(input_word2.value.trim() == ''){
		var dataset = [{label: `${query1}`, data: word_freq1.map(x => x[1]), backgroundColor: "#75baff"}];
	}else{
		var word_freq2 = data.word_freq2; 
		var query2 = input_word2.value;
		var dataset = [
			{label: `${query1}`, data: word_freq1.map(x => x[1]), backgroundColor: "#75baff"},
			{label: `${query2}`, data: word_freq2.map(x => x[1]), backgroundColor: "#ff8ce8"}
		];
	}

	////////// draw chart //////////
	new Chart(chartChart, {
		type: "bar",
		data: {
			labels: word_freq1.map(x => x[0] + ` (${x[2]}sec)`), // twitter (12sec)
			datasets: dataset
		},
		options: {
			responsive: true,
			title: {
				display: true,
				text: "word frequecy / 1M words (fetch time)"
			},
			scales: {
				yAxes: [{
					ticks: {
						beginAtZero:true
					}
				}]
			}
		}
	});

	///////// create ngram table //////////
	if(input_word2.value.trim()==""){ // search by only one word
		result_oneword.style.display = ""; // show result row
		result_oneword_input.innerText = input_word1.value;
		result_n_left.innerText = n_left.value;
		result_n_right.innerText = n_right.value;
		table_oneword.innerHTML = ""; // initinalize table 
		for(i=0; i<data.ngrams1.length; i++){ // ngrams1 = [[ngramL, count, ngramR, count],...]
			ngramL = data.ngrams1[i][0].replace(/</g, "&lt;").replace(/>/g, "&gt;"); // replave < > with &lt; &gt;
			countL = data.ngrams1[i][1];
			ngramR = data.ngrams1[i][2].replace(/</g, "&lt;").replace(/>/g, "&gt;");
			countR = data.ngrams1[i][3];
			// show popover to continue to search word/string 
			table_oneword.innerHTML += `
			<tr class="table">
				<td class="center ngramL">
					<span tabindex="-1"  data-trigger="focus" class="pointer"data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramL.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramL.replace(/ /g,'').replace(/\|/g,'').replace(/__/g,' ')}</span>'>
						${ngramL}
					</span>
				</td> 
				<td class="center ngramL2">${countL}</td>
				<td class="center ngramR">
					<span tabindex="-1"  data-trigger="focus" class="pointer" data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramR.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramR.replace(/ /g,'').replace(/\|/g,'').replace(/__/g,' ')}</span>'>
						${ngramR}
					</span>
				</td>
				<td class="center ngramR2">${countR}</td>
			</tr>`;
		}
	
	}else{ // search by two words
		result_twoword.style.display = "";
		result_twoword_input1.innerText = input_word1.value;
		result_twoword_input2.innerText = input_word2.value;
		result_n_left1.innerText = n_left.value;
		result_n_right1.innerText = n_right.value;
		result_n_left2.innerText = n_left.value;
		result_n_right2.innerText = n_right.value;
		table_twoword1.innerHTML = ""; // initinalize table 
		table_twoword2.innerHTML = "";
		for(i=0; i<data.ngrams1.length; i++){
			ngramL = data.ngrams1[i][0].replace(/</g, "&lt;").replace(/>/g, "&gt;"); // replave < > with &lt; &gt;
			countL = data.ngrams1[i][1];
			ngramR = data.ngrams1[i][2].replace(/</g, "&lt;").replace(/>/g, "&gt;");
			countR = data.ngrams1[i][3];
			// show popover to continue to search word/string 
			table_twoword1.innerHTML += `
			<tr class="table">
				<td class="center ngramL">
					<span tabindex="-1"  data-trigger="focus" class="pointer"data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramL.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramL.replace(/ /g,'').replace(/\|/g,'')}</span>'>
						${ngramL}
					</span>
				</td> 
				<td class="center ngramL2">${countL}</td>
				<td class="center ngramR">
					<span tabindex="-1"  data-trigger="focus" class="pointer" data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramR.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramR.replace(/ /g,'').replace(/\|/g,'')}</span>'>
						${ngramR}
					</span>
				</td>
				<td class="center ngramR2">${countR}</td>
			</tr>`;
		}
		for(i=0; i<data.ngrams2.length; i++){
			ngramL = data.ngrams2[i][0].replace(/</g, "&lt;").replace(/>/g, "&gt;"); // replave < > with &lt; &gt;
			countL = data.ngrams2[i][1];
			ngramR = data.ngrams2[i][2].replace(/</g, "&lt;").replace(/>/g, "&gt;");
			countR = data.ngrams2[i][3];
			// show popover to continue to search word/string 
			table_twoword2.innerHTML += `
			<tr class="table">
				<td class="center ngramL">
					<span tabindex="-1"  data-trigger="focus" class="pointer"data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramL.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramL.replace(/ /g,'').replace(/\|/g,'')}</span>'>
						${ngramL}
					</span>
				</td> 
				<td class="center ngramL2">${countL}</td>
				<td class="center ngramR">
					<span tabindex="-1"  data-trigger="focus" class="pointer" data-toggle="popover" 
						data-content='continue to search?
							<br>by multiple words: <span class="pointer text-danger" onclick=continue_search_word(this)>${ngramR.replace(/ /g,'|')}</span>
							<br>by string: <span class="pointer text-primary" onclick=continue_search_string(this)>${ngramR.replace(/ /g,'').replace(/\|/g,'')}</span>'>
						${ngramR}
					</span>
				</td>
				<td class="center ngramR2">${countR}</td>
			</tr>`;
		}
	}
	$('body [data-toggle="popover"]').popover({html:true, sanitize: false}); // reactivate popovers, sanitize=false because embbed html in popover
}

function continue_search_word(elem){
	document.body.focus();
	use_multiple_words.checked = true;
	input_word1.value = elem.innerText;
	input_word2.value = '';
	start_ajax('word');
}

function continue_search_string(elem){
	document.body.focus();
	console.log(elem.previousElementSibling.previousElementSibling.innerText); // 2 previous element = multiple word search
	switch_regex.checked = false;
	input_string1.value = elem.innerText;
	input_string2.value = '';
	input3.value = elem.previousElementSibling.previousElementSibling.innerText;
	start_ajax('word_to_string');
}


////////////////////////////// SHOW RESULT: SEARCH BY STRING //////////////////////////////

function show_result_string(data, mode){
	if(input_string2.value.trim()=="" || mode=="word_to_string"){ // search by only one string
		result_onestring.style.display = ""; // show result row
		result_onestring_input.innerText = (mode=="string")? input_string1.value : input3.value; // title of the table
		result_onestring_num.innerText = data.results1.length; // num of result
		table_onestring.innerHTML = ""; // initinalize table
		(data.results1.length > 20)? btn_show_more0.style.display = "" : btn_show_more0.style.display = "none"; // show more button
		for(i=0; i<data.results1.length; i++){
			if(i<20){
				table_onestring.innerHTML +=
				`<tr class="table">
					<td class="center">${data.results1[i][0]}</td> 
					<td class="center">${data.results1[i][1]}</td>
				</tr>`;
			}else{
				table_onestring.innerHTML +=
				`<tr class="table hidden_result0">
					<td class="center">${data.results1[i][0]}</td>
					<td class="center">${data.results1[i][1]}</td>
				</tr>`;
			}
		}
		
	}else{ // search by two strings
		result_twostring.style.display = ""; // show result row
		result_twostring_input1.innerText = input_string1.value;
		result_twostring_input2.innerText = input_string2.value;
		result_twostring_num1.innerText = data.results1.length;
		result_twostring_num2.innerText = data.results2.length;
		table_twostring1.innerHTML = ""; // initinalize table
		table_twostring2.innerHTML = "";
		btn_show_more1.style.display = (data.results1.length > 20)?  "" : "none";
		btn_show_more2.style.display = (data.results2.length > 20)?  "" : "none";
		for(i=0; i<data.results1.length; i++){
			if(i<20){
				table_twostring1.innerHTML +=
				`<tr class="table">
					<td class="center">${data.results1[i][0]}</td>
					<td class="center">${data.results1[i][1]}</td>
				</tr>`;
			}else{
				table_twostring1.innerHTML +=
				`<tr class="table hidden_result1">
					<td class="center">${data.results1[i][0]}</td>
					<td class="center">${data.results1[i][1]}</td>
				</tr>`;
			}
		}
		for(i=0; i<data.results2.length; i++){
			if(i<20){
				table_twostring2.innerHTML +=
				`<tr class="table">
					<td class="center">${data.results2[i][0]}</td>
					<td class="center">${data.results2[i][1]}</td>
				</tr>`;
			}else{
				table_twostring2.innerHTML +=
				`<tr class="table hidden_result2">
					<td class="center">${data.results2[i][0]}</td>
					<td class="center">${data.results2[i][1]}</td>
				</tr>`;
			}
		}
	}
}

function show_more(n){
	event.target.blur(); // unforcus button
	current_X = window.scrollX;
	current_Y = window.scrollY;
	let hidden = document.getElementsByClassName(`hidden_result${n}`); // get hidden <tr>
	if(hidden.length<=20){
		document.getElementById(`btn_show_more${n}`).style.display = "none";
	}
	Array.from(hidden).slice(0,20).forEach(x => x.classList.remove(`hidden_result${n}`));
	// scroll to original position
	window.scrollTo(current_X, current_Y);
}
