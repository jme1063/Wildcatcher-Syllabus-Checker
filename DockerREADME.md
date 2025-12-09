# DockerREADME
Created by: Jacqueline Ebel, Fall 2025 Team Alpha

## Building and Running the Docker Container

This guide explains how to build and run the Docker container for this project on the vm, but it can be run locally basically the same way for development.

---

## Prerequisites
- Docker must be installed on your machine or VM.
- You must have access to the project files (including Dockerfile and requirements.txt).
- For remote VM: You need SSH access and Docker installed on the VM (it was by default, dont worry)
  - you will also need to clone the repo in your user directory on the VM. `Only one person on the team should be responsible for the docker container on the VM`, otherwise you will conflict when multiple containers are vying for the same port.

---

## Build & Run

### 1. SSH into the VM
First, ssh into the vm using your user id

`ssh username@whitemount.sr.unh.edu`


### 2. Make a copy of the project
You will be making a copy of the repo in your user dir in the VM. If you've never used git before, you do have to log into your account on the VM first. When cloning, make sure you chose the `SSH` tab in the clone menu when making your url on github


#### If you have 2FA enabled on your git account:
`You will need to make a github ssh key` if you have 2fa enabled on git, otherwise you wont be able to verify it is you to git when you attempt to clone the repo due to the server restrictions. You can try cloning it normally first, but if you have trouble this is how I did it.

**Process**
  1. Log into git on the VM

  2. Generate a new SSH key on the terminal in the directory you are making the project
    - `ssh-keygen -t ed25519 -C "your_email@example.com"`, where the email is your github account email.
    - press enter to accept the file location
  
  3. Add the SSH key generated to your "agent" (the thing that will make the full key)
    - `eval "$(ssh-agent -s)"`
    - `ssh-add ~/.ssh/id_ed25519`
  
  4. Copy this key to use on the git website:
    - `cat ~/.ssh/id_ed25519.pub` and copy what it gives. it should show
    a key that looks similar to "SHA###:Escub5fxbjdGAL18C4bLwSBTjCWggM+RWjJEsv+jGH4"

  5. Add this to github:
  On the github site:
  - Click on your user icon in git and go to settigns
  - in settings, on the left hand side under `Access`, click on `SSH and GPG keys`
  - Click on the green button on top called `New SSH Key`
  - the title can be literally anything you will remember, the type is `authentication key` (should just be the default), and in the giant box, you're going to paste the key you generated on the vm
  
  6. now you can clone the repo on git. You're going to select the `SSH` link when you copy the link for cloning, and you will now clone as normal


### 3. Build the Docker Image on the VM
Navigate to your project directory:

`cd /home/user/[your user id]/[project-name]`

Build the image:

`docker build -t syllabus-checker .`

- This command builds the Docker image and names it `syllabus-checker`.
- the `.` at the end dictates where to build the docker container. `.` means in the working dir
- You may have to wait a moment for docker to install the required dependencies listed in the requirements file.

### 4. Run the Docker Container on the VM
`docker run -p 8001:8001 syllabus-checker`


- ensures use of the port 8001, as with the Fall 2025 class thats the port we were using
- Access the app at `https://whitemount-t1.sr.unh.edu` 

You may find it useful alternatively to run:


`nohup docker run -p 8001:8001 sylabus-checker > runtime.log 2>&1 &`


- nohup means that you will still continue to run the program even when the terminal shuts down.
- you will also be saving the runtime log to your directory. This is useful for debugging, though we never used it much in Fall 2025. You can use `vim` in order to view the log in the vm

## Useful Commands
- List images: `docker images`
- List running containers: `docker ps`
- Stop a container: `docker stop <container_id>`
- Remove a container: `docker rm <container_id>`
- Remove an image: `docker rmi <image_id>`

---

## Notes
- If you change requirements.txt or Dockerfile, rebuild the image.
- If you log out of the vm, the container will still run. use `docker ps` to see all running containers on vm to verify
- if you need to stop the container (to rebuild), use `docker stop [container ID or name]` 
---

## Troubleshooting
- If you see missing package errors, check requirements.txt and rebuild.
- If the container won't start, check logs with:
  ```
  docker logs <container_id>
  ```


