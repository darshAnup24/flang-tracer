! C08: Coarray sync + get
program coarray_sync
    implicit none
    integer :: my_val[*]
    integer :: remote_val
    
    my_val = this_image()
    ! The construct below will be traced
    sync all
    
    if (num_images() > 1) then
        if (this_image() == 1) then
            remote_val = my_val[2]
        end if
    end if
end program coarray_sync
